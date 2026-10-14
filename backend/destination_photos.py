import html
import json
import re
import time
from collections import OrderedDict
from threading import Lock
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_cache = OrderedDict()
_lock = Lock()


def _query(parameters):
    url = 'https://en.wikipedia.org/w/api.php?' + urlencode({
        'action': 'query', 'format': 'json', 'formatversion': 2, **parameters,
    })
    request = Request(url, headers={'User-Agent': 'GhostTravel/1.0 (destination photo lookup)',
                                    'Accept': 'application/json'})
    with urlopen(request, timeout=8) as response:
        return json.load(response).get('query', {}).get('pages', [])


def _plain_text(value):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', '', value)).split())


def destination_photos(destination):
    key = destination.casefold()
    with _lock:
        saved = _cache.get(key)
        if saved and time.monotonic() - saved[0] < 86400:
            return saved[1]

    city = destination.split(',')[0].strip()
    country = destination.split(',', 1)[1].strip() if ',' in destination else ''
    pages = _query({'generator': 'search', 'gsrsearch': f'intitle:"{city}" {country}',
                    'gsrnamespace': 0, 'gsrlimit': 3, 'prop': 'pageimages|images',
                    'piprop': 'name', 'pilicense': 'free', 'imlimit': 40})
    pages.sort(key=lambda page: page.get('index', 999))
    # Require the city name in the article title to avoid unrelated search results.
    page = next((page for page in pages if page.get('pageimage') and
                 city.casefold() in page.get('title', '').casefold()), None)
    photos = []
    if page:
        titles = ['File:' + page['pageimage']] + [item['title'] for item in page.get('images', [])]
        titles = list(dict.fromkeys(title for title in titles
                      if re.search(r'\.(jpe?g|png)$', title, re.I)
                      and not re.search(r'flag|logo|coat.of.arms|map|icon|locator', title, re.I)))[:16]
        files = _query({'titles': '|'.join(titles), 'prop': 'imageinfo',
                        'iiprop': 'url|extmetadata|size|mime', 'iiurlwidth': 960}) if titles else []
        normalized_titles = [title.replace('_', ' ') for title in titles]
        files.sort(key=lambda item: normalized_titles.index(item.get('title', '').replace('_', ' '))
                   if item.get('title', '').replace('_', ' ') in normalized_titles else 999)
        for item in files:
            if not item.get('imageinfo'):
                continue
            image = item['imageinfo'][0]
            if image.get('mime', 'image/jpeg') not in ('image/jpeg', 'image/png'):
                continue
            if image.get('width', 1000) < 600:
                continue
            metadata = image.get('extmetadata', {})
            artist = _plain_text(metadata.get('Artist', {}).get('value', ''))
            license_name = _plain_text(metadata.get('LicenseShortName', {}).get('value', ''))
            url = image.get('thumburl') or image.get('url', '')
            source = image.get('descriptionurl', '')
            if artist and license_name and url.startswith('https://') and source.startswith('https://'):
                caption = _plain_text(metadata.get('ObjectName', {}).get('value', ''))
                if not caption or len(caption) > 150:
                    caption = re.sub(r'\.(jpe?g|png)$', '', item.get('title', page['title']).removeprefix('File:'), flags=re.I).replace('_', ' ')
                photos.append({'url': url.split('?')[0], 'destination': destination, 'title': caption,
                               'artist': artist, 'license': license_name, 'source_url': source})
                if len(photos) == 6:
                    break
    with _lock:
        _cache[key] = (time.monotonic(), photos)
        _cache.move_to_end(key)
        while len(_cache) > 200:
            _cache.popitem(last=False)
    return photos


def destination_photo(destination):
    photos = destination_photos(destination)
    return photos[0] if photos else None
