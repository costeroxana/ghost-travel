import json
import logging
import os
from urllib.parse import urlencode

import requests
from crewai.tools import BaseTool


def _get(path, key, **params):
    response = requests.get(
        f'https://api.latlng.work{path}?{urlencode(params)}',
        headers={'X-Api-Key': key},
        timeout=(3, 5),
        allow_redirects=False,
    )
    response.raise_for_status()
    return response.json()


class FindNearbyCafes(BaseTool):
    name: str = 'find_nearby_cafes'
    description: str = (
        'Find named OpenStreetMap cafes within 800 meters of an attraction. '
        'Provide the attraction name and the trip destination including the country if known.'
    )

    def _run(self, attraction: str, destination: str) -> str:
        return json.dumps(find_cafes(f'{attraction}, {destination}'))


def find_cafes(location: str) -> dict:
    key = os.getenv('LATLNG_API_KEY', '').strip()
    if not key:
        return {'status': 'unavailable'}
    try:
        features = _get('/api', key, q=location, limit=1)['features']
        if not features:
            return {'status': 'location_not_found'}
        lon, lat = features[0]['geometry']['coordinates']
        places = _get(
            '/v1/places/nearby', key, lat=lat, lon=lon, radius=800,
            category='cafe', limit=5,
        )['places']
        cafes = [
            {'name': place['name'], 'distance_m': place.get('distance_m')}
            for place in places
            if place.get('name') and place.get('category') == 'cafe'
        ]
        return {'status': 'ok', 'source': 'OpenStreetMap', 'cafes': cafes}
    except (requests.RequestException, KeyError, TypeError, ValueError, AttributeError) as error:
        logging.getLogger(__name__).warning('Cafe lookup failed (%s)', type(error).__name__)
        return {'status': 'unavailable'}
