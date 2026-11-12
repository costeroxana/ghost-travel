"""Build and query a local search index of Wikivoyage articles."""

import argparse
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


DEFAULT_INDEX = Path(__file__).with_name('wikivoyage_guides.sqlite3')
HEADINGS = ('h2', 'h3', 'h4', 'h5', 'h6')
EDITIONS = {'en', 'ro', 'es', 'fr', 'de', 'it'}


def fetch_article(title, language='en'):
    if language not in EDITIONS:
        raise ValueError('Unsupported Wikivoyage edition')
    params = {'action': 'parse', 'format': 'json', 'formatversion': 2,
              'prop': 'text|revid', 'page': title, 'redirects': 1}
    request = Request(f'https://{language}.wikivoyage.org/w/api.php?{urlencode(params)}',
                      headers={'User-Agent': 'GhostTravel/0.1 (Wikivoyage guide index)'})
    with urlopen(request, timeout=4) as response:
        result = json.load(response)
    if result.get('error', {}).get('code') in {'missingtitle', 'invalidtitle'}:
        return None
    article = result.get('parse')
    if not isinstance(article, dict):
        raise ValueError('Wikivoyage did not return an article')
    return article['title'], article['revid'], article['text']


def extract_passages(title, html, revision, language='en'):
    document = BeautifulSoup(html, 'html.parser')
    article = f'https://{language}.wikivoyage.org/wiki/{quote(title.replace(" ", "_"))}?oldid={revision}'
    for element in document.select('.mw-editsection, .reference, figure, table, style, script'):
        element.decompose()
    section = anchor = ''
    for block in document.find_all([*HEADINGS, 'p', 'li']):
        if block.name in HEADINGS:
            marker = block.find(class_='mw-headline') or block
            anchor = marker.get('id', '')
            section = marker.get_text(' ', strip=True)
        elif anchor and not block.find_parent(['li', 'nav']):
            # Index top-level entries without duplicating nested lists.
            for nested_list in block.find_all(['ul', 'ol']):
                nested_list.extract()
            text = ' '.join(block.get_text(' ', strip=True).split())
            if text:
                yield (section, f'{article}#{quote(anchor)}', text)


def guide_key(title, language):
    return language + ':' + ' '.join(title.replace('_', ' ').split()).casefold()


def build_index(path, title, html, revision, requested_title=None, language='en'):
    passages = list(extract_passages(title, html, revision, language))
    if not passages:
        raise ValueError('No linked passages found in the Wikivoyage article')
    with closing(sqlite3.connect(path)) as database, database:
        database.execute('BEGIN')
        database.execute('CREATE TABLE IF NOT EXISTS guide_aliases ('
                         'alias TEXT PRIMARY KEY, guide TEXT NOT NULL)')
        database.execute('CREATE VIRTUAL TABLE IF NOT EXISTS passages USING fts5('
                         'guide UNINDEXED, section, url UNINDEXED, text)')
        guide = guide_key(title, language)
        database.execute('DELETE FROM passages WHERE guide = ?', (guide,))
        database.executemany('INSERT INTO passages VALUES (?, ?, ?, ?)',
                             ((guide, *passage) for passage in passages))
        database.executemany('INSERT OR REPLACE INTO guide_aliases VALUES (?, ?)',
                             [(guide, guide), (guide_key(requested_title or title, language), guide)])
    return len(passages)


def search_index(path, title, query, limit=5, language='en'):
    # Use literal words so punctuation and FTS operators in preferences stay data.
    words = dict.fromkeys(re.findall(r'[^\W_]+', query.casefold()))
    if {'coffee', 'café', 'cafe', 'cafés', 'cafes'} & words.keys():
        for word in ('visit', 'all', 'shop', 'shops'):
            words.pop(word, None)
        words.update(dict.fromkeys(('coffee', 'café', 'cafés', 'cafenea', 'cafenele')))
    terms = ' OR '.join(f'"{word}"' for word in words if len(word) > 2)
    if not Path(path).is_file():
        return []
    with closing(sqlite3.connect(path)) as database:
        database.row_factory = sqlite3.Row
        rows = database.execute(
            'SELECT section, url, substr(text, 1, 1200) AS text FROM passages WHERE '
            + ('passages MATCH ? AND ' if terms else '')
            + 'guide = (SELECT guide FROM guide_aliases WHERE alias = ?) '
            + ('ORDER BY bm25(passages), rowid LIMIT ?' if terms else 'ORDER BY rowid LIMIT ?'),
            (*([terms] if terms else []), guide_key(title, language), limit),
        )
        return [dict(row) for row in rows]


def retrieve_guide(path, destination, preferences, language, fetch=False):
    city, separator, region = destination.partition(',')
    # Try the disambiguated title before the short title used by most city guides.
    titles = (destination, f'{city} ({region.strip()})', city) if separator else (city,)
    editions = (language, 'en') if language != 'en' else ('en',)
    for edition in editions:
        for title in titles:
            passages = search_index(path, title, preferences, language=edition)
            if passages:
                return passages
            # A previously indexed guide can still supply general context.
            general = search_index(path, title, '', language=edition)
            if general:
                return general
            if fetch and (article := fetch_article(title, edition)):
                canonical, revision, html = article
                build_index(path, canonical, html, revision, title, edition)
                return (search_index(path, title, preferences, language=edition)
                        or search_index(path, title, '', language=edition))
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, default=DEFAULT_INDEX)
    parser.add_argument('--language', choices=sorted(EDITIONS), default='en')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('build').add_argument('title')
    search = commands.add_parser('search')
    search.add_argument('title')
    search.add_argument('query')
    args = parser.parse_args()
    if args.command == 'build':
        article = fetch_article(args.title, args.language)
        if article is None:
            parser.error(f'Wikivoyage could not load {args.title!r}')
        title, revision, html = article
        count = build_index(args.index, title, html, revision, args.title, args.language)
        print(f'Indexed {count} passages from Wikivoyage: {title} (revision {revision}).')
    else:
        passages = search_index(args.index, args.title, args.query, language=args.language)
        print(json.dumps(passages, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
