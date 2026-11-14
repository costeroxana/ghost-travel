"""Fetch dated Google Flights results through SerpApi."""

import json
import logging
import os
import re

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, PrivateAttr


def _search(key, engine, **params):
    response = requests.get(
        'https://serpapi.com/search.json',
        params={'api_key': key, 'engine': engine, **params},
        timeout=(3, 7),
        allow_redirects=False,
    )
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict) or result.get('error'):
        raise ValueError('Invalid SerpApi result')
    return result


def _location(key, city):
    if re.fullmatch(r'[A-Z]{3}', city):
        return city
    suggestions = _search(key, 'google_flights_autocomplete', q=city, gl='ro').get('suggestions', [])
    return next((item['id'] for item in suggestions
                 if item.get('type') == 'city' and item.get('id') and item.get('airports')), None)


def search_flights(origin, destination, departure_date):
    """Return up to three outbound options for one adult, with provider prices."""
    key = os.getenv('SERPAPI_API_KEY', '').strip()
    if not key or not departure_date:
        return 'unavailable', []

    try:
        departure_id = _location(key, origin)
        arrival_id = _location(key, destination)
        if not departure_id or not arrival_id or departure_id == arrival_id:
            return 'location_not_found', []
        data = _search(
            key, 'google_flights', departure_id=departure_id, arrival_id=arrival_id,
            outbound_date=departure_date, type=2, currency='EUR', adults=1, gl='ro',
        )
        options = []
        seen = set()
        for option in data.get('best_flights', []) + data.get('other_flights', []):
            legs = option['flights']
            price = option.get('price')
            if not legs or type(price) is not int or price <= 0:
                continue
            segments = [
                f"{leg['flight_number']} {leg['departure_airport']['id']} "
                f"{leg['departure_airport']['time']} → {leg['arrival_airport']['id']} "
                f"{leg['arrival_airport']['time']}"
                for leg in legs
            ]
            route = ' / '.join(segments)
            if route in seen:
                continue
            seen.add(route)
            options.append({'route': route, 'estimate': f'€{price}'})
            if len(options) == 3:
                break
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as error:
        logging.getLogger(__name__).warning('SerpApi flight lookup failed (%s)', type(error).__name__)
        return 'unavailable', []

    return ('ok' if options else 'no_results'), options


class SearchFlightsInput(BaseModel):
    pass


class SearchFlights(BaseTool):
    name: str = 'search_flights'
    description: str = 'Find outbound flights for one adult in EUR for the current trip. Takes no arguments.'
    args_schema: type[BaseModel] = SearchFlightsInput
    _trip: tuple[str, str, str | None] | None = PrivateAttr(default=None)
    _result: dict | None = PrivateAttr(default=None)

    def set_trip(self, origin, destination, departure_date):
        self._trip = (origin, destination, departure_date)
        self._result = None

    @property
    def result(self):
        return self._result

    def _run(self) -> str:
        if self._result is None:
            status, options = search_flights(*self._trip) if self._trip else ('unavailable', [])
            self._result = {'status': status, 'options': options}
        return json.dumps(self._result, ensure_ascii=False)
