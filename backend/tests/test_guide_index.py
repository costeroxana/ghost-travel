import tempfile
import unittest
from pathlib import Path

from guide_index import build_index, search_index


class GuideIndexTests(unittest.TestCase):
    def test_search_returns_revision_specific_sections(self):
        html = '''
        <div class="mw-heading"><h3 id="Museums">Museums</h3></div>
        <ol><li>Village Museum displays traditional Romanian buildings.</li></ol>
        <h4><span class="mw-headline" id="Parks">Parks</span></h4>
        <ol><li>Herăstrău Park is home to the Village Museum.</li></ol>
        '''
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            index = Path(directory) / 'guide.sqlite3'
            self.assertEqual(search_index(index, 'Bucharest', 'Village Museum'), [])
            self.assertEqual(build_index(index, 'Bucharest', html, 123, 'București'), 2)
            build_index(index, 'Paris', '<h2 id="Parks">Parks</h2><p>Paris park.</p>', 999)
            results = search_index(index, 'București', 'Village Museum and a nearby park')
            self.assertEqual({row['section'] for row in results}, {'Museums', 'Parks'})
            for row in results:
                self.assertTrue(row['url'].endswith(f'?oldid=123#{row["section"]}'))
            build_index(index, 'Bucharest', html, 456)
            results = search_index(index, 'Bucharest', '"Village Museum" OR (park)')
            self.assertEqual(len(results), 2)
            self.assertTrue(all('?oldid=456#' in row['url'] for row in results))
            self.assertIn('/Paris?oldid=999#Parks', search_index(index, 'Paris', 'park')[0]['url'])
            self.assertEqual(search_index(index, 'Rome', 'park'), [])
