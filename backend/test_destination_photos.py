import unittest
from unittest.mock import patch

import destination_photos as photos


class DestinationPhotoTests(unittest.TestCase):
    def setUp(self):
        photos._cache.clear()
        self.pages = [{'title': 'Rome', 'pageimage': 'Rome.jpg', 'index': 1}]
        self.image = [{'imageinfo': [{
            'thumburl': 'https://upload.wikimedia.org/rome.jpg',
            'descriptionurl': 'https://commons.wikimedia.org/wiki/File:Rome.jpg',
            'extmetadata': {'Artist': {'value': '<a href="/wiki/User:Example">Example</a>'},
                            'LicenseShortName': {'value': 'CC BY 3.0'}},
        }]}]

    def test_attributed_photo_is_cached_and_refreshed_daily(self):
        with patch.object(photos, '_query', side_effect=[self.pages, self.image, self.pages, self.image]) as query:
            with patch.object(photos.time, 'monotonic', return_value=100):
                photo = photos.destination_photo('Rome, Italy')
            self.assertEqual(photo['artist'], 'Example')
            with patch.object(photos.time, 'monotonic', return_value=101):
                self.assertEqual(photos.destination_photo('rome, italy'), photo)
            self.assertEqual(query.call_count, 2)
            with patch.object(photos.time, 'monotonic', return_value=86500):
                photos.destination_photo('Rome, Italy')
            self.assertEqual(query.call_count, 4)

    def test_unrelated_search_results_are_not_shown(self):
        with patch.object(photos, '_query', return_value=[{'title': 'Some other city', 'pageimage': 'Other.jpg'}]):
            self.assertIsNone(photos.destination_photo('Rome, Italy'))

    def test_missing_photo_or_credit_is_handled(self):
        with patch.object(photos, '_query', return_value=[]):
            self.assertIsNone(photos.destination_photo('Unknown City'))
        with patch.object(photos, '_query', side_effect=[self.pages, [{'imageinfo': [{'url': 'https://example.com/photo.jpg'}]}]]):
            self.assertIsNone(photos.destination_photo('Rome, Italy'))

    def test_gallery_returns_multiple_photos_and_filters_icons(self):
        pages = [{'title': 'Rome', 'pageimage': 'Rome.jpg', 'index': 1,
                  'images': [{'title': 'File:Colosseum.jpg'}, {'title': 'File:Flag of Rome.png'}]}]
        images = []
        for name in ['Rome.jpg', 'Colosseum.jpg']:
            image = dict(self.image[0]['imageinfo'][0])
            image['thumburl'] = f'https://upload.wikimedia.org/{name}'
            images.append({'title': f'File:{name}', 'imageinfo': [image]})
        with patch.object(photos, '_query', side_effect=[pages, images]) as query:
            gallery = photos.destination_photos('Rome, Italy')
        self.assertEqual(len(gallery), 2)
        self.assertNotIn('Flag', query.call_args.args[0]['titles'])
        self.assertEqual(gallery[0]['title'], 'Rome')


if __name__ == '__main__':
    unittest.main()
