import json
import logging
import os
from typing import Annotated, Literal
from urllib.parse import urlencode

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, PrivateAttr, StringConstraints


def _get(path, key, **params):
    response = requests.get(
        f'https://api.latlng.work{path}?{urlencode(params)}',
        headers={'X-Api-Key': key},
        timeout=(3, 5),
        allow_redirects=False,
    )
    response.raise_for_status()
    return response.json()


class FindPlacesInput(BaseModel):
    city: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
    category: Literal['museum']


def find_places(city: str, category: str) -> dict:
    args = FindPlacesInput(city=city, category=category)
    category_name = args.category

    key = os.getenv('LATLNG_API_KEY', '').strip()
    if not key:
        return {'status': 'unavailable', 'places': []}

    try:
        features = _get('/api', key, q=args.city, limit=1)['features']
        if not features:
            return {'status': 'location_not_found', 'places': []}

        lon, lat = features[0]['geometry']['coordinates']
        nearby = _get(
            '/v1/places/nearby', key, lat=lat, lon=lon, radius=5000,
            category=category_name, limit=5,
        )['places']
        places = [
            {'name': place['name'], 'category': category_name, 'distance_m': place.get('distance_m')}
            for place in nearby
            if place.get('name') and place.get('category') == category_name
        ]
    except (requests.RequestException, KeyError, TypeError, ValueError, AttributeError) as error:
        logging.getLogger(__name__).warning('LatLng museum lookup failed (%s)', type(error).__name__)
        return {'status': 'unavailable', 'places': []}

    return {'status': 'ok' if places else 'no_results', 'source': 'OpenStreetMap via LatLng', 'places': places}


class FindPlaces(BaseTool):
    name: str = 'find_places'
    description: str = (
        'Look up named museums near the trip destination through the LatLng API. '
        'Pass the requested trip destination as city and museum as category.'
    )
    args_schema: type[BaseModel] = FindPlacesInput
    _returned_names: set[str] = PrivateAttr(default_factory=set)
    _results_by_city: dict[str, dict] = PrivateAttr(default_factory=dict)

    @property
    def returned_names(self) -> set[str]:
        return self._returned_names

    def _run(self, city: str, category: str) -> str:
        args = FindPlacesInput(city=city, category=category)
        city_key = ','.join(' '.join(part.split()) for part in args.city.casefold().split(','))
        if city_key not in self._results_by_city:
            result = find_places(args.city, args.category)
            self._results_by_city[city_key] = result
            self._returned_names.update(place['name'] for place in result['places'])
        result = self._results_by_city[city_key]
        return json.dumps(result, ensure_ascii=False)
