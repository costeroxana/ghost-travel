import os
import math
import re
import time
from decimal import Decimal
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from collections import deque
from threading import Lock
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from itinerary_cache import read_itinerary, request_key, save_itinerary
from destination_photos import destination_photos
from agent_metrics import measured_generation
from crew.itinerary_models import (
    FlightResearch, LocalResearch, Itinerary, ItineraryValidationError,
    credit_museum_sources, parse_crew_itinerary, prepare_itinerary, render_itinerary, budget_summary,
)
from crew_loader import create_travel_crew

# 1. Load environment settings from .env.
load_dotenv()

print("🧠 Initializing Ghost Travel Agent...")

# Defaults for clients that do not specify a route.
destination = "Rome, Italy"
origin = "Bucharest, Romania"
# Load the agent definitions after environment settings are available.
travel_crew = create_travel_crew()

# Expose the backend API for the React Native app.
app = Flask(__name__)
CORS(app) # Allow cross-origin requests from the mobile and web app.
app.config['AGENT_METRICS_PATH'] = os.path.join(os.path.dirname(__file__), 'agent_metrics.sqlite3')
app.config['ITINERARY_CACHE_PATH'] = os.path.join(os.path.dirname(__file__), 'itinerary_cache.sqlite3')

# Shared across callers in this process, so changing IP addresses cannot bypass the limit.
_request_times = deque()
_rate_limit_lock = Lock()
_crew_lock = Lock()
_rate_limit_requests = 5
_rate_limit_window = 60


# Limit costly, uncached itinerary generations to 5 requests per rolling minute in this process.
def limit_generation():
    with _rate_limit_lock:
        now = time.monotonic()
        while _request_times and now - _request_times[0] >= _rate_limit_window:
            _request_times.popleft()
        if len(_request_times) >= _rate_limit_requests:
            retry_after = max(1, math.ceil(_rate_limit_window - (now - _request_times[0])))
            return jsonify(error='Rate limit exceeded.'), 429, {'Retry-After': str(retry_after)}
        _request_times.append(now)

    return None

@app.get('/api/destination-photos')
def get_destination_photos():
    destination_name = ' '.join(request.args.get('destination', '').split())
    if not 2 <= len(destination_name) <= 100:
        return jsonify(error='Enter a destination between 2 and 100 characters.'), 400
    try:
        return jsonify(photos=destination_photos(destination_name))
    except Exception:
        app.logger.warning('Destination gallery provider is unavailable', exc_info=True)
        return jsonify(error='Photos are temporarily unavailable. Please try again.'), 503


@app.route('/api/itinerary', methods=['GET', 'POST'])
def get_itinerary_for_app():
    if request.method == 'POST':
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error='Send a JSON object with origin and destination.'), 400
    else:
        # Preserve the original demo for clients that do not send a route yet.
        payload = request.args.to_dict()
        payload.setdefault('origin', origin)
        payload.setdefault('destination', destination)

    route = {}
    for field in ('origin', 'destination'):
        value = payload.get(field)
        if not isinstance(value, str) or any(ord(char) < 32 for char in value):
            return jsonify(error=f'Please enter a valid {field} city.'), 400
        value = ' '.join(value.split())
        if not 2 <= len(value) <= 100:
            return jsonify(error=f'{field.capitalize()} must contain 2 to 100 characters.'), 400
        route[field] = value
    if route['origin'].casefold() == route['destination'].casefold():
        return jsonify(error='Choose a destination different from your departure city.'), 400

    raw_budget = str(payload.get('budget', 300)).strip()
    if not re.fullmatch(r'[0-9]{1,6}(?:\.[0-9]{1,2})?', raw_budget):
        return jsonify(error='Enter a budget in EUR with up to two decimal places.'), 400
    trip_budget = Decimal(raw_budget)
    if not Decimal('1') <= trip_budget <= Decimal('100000'):
        return jsonify(error='The total budget must be between EUR 1 and EUR 100,000.'), 400

    raw_days = str(payload.get('days', 3)).strip()
    if not re.fullmatch(r'[0-9]{1,2}', raw_days) or not 1 <= int(raw_days) <= 30:
        return jsonify(error='Choose a whole number of days between 1 and 30.'), 400
    trip_days = int(raw_days)

    departure_date = payload.get('departure_date')
    end_date = None
    if departure_date is not None:
        try:
            if not isinstance(departure_date, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', departure_date):
                raise ValueError('Invalid date format')
            selected_date = date.fromisoformat(departure_date)
            # Use the service's local date when deciding whether a departure is in the past.
            if selected_date < datetime.now(ZoneInfo('Europe/Bucharest')).date():
                return jsonify(error='Choose a departure date today or later.'), 400
            end_date = (selected_date + timedelta(days=trip_days - 1)).isoformat()
        except (ValueError, OverflowError):
            return jsonify(error='Enter a valid departure date in YYYY-MM-DD format.'), 400

    languages = {'en': ('English', 'Day'), 'ro': ('Romanian', 'Ziua'),
                 'es': ('Spanish', 'Día'), 'fr': ('French', 'Jour'),
                 'de': ('German', 'Tag'), 'it': ('Italian', 'Giorno')}
    language_code = payload.get('language', 'en')
    if not isinstance(language_code, str) or language_code not in languages:
        return jsonify(error='Please choose a supported language.'), 400
    language_name, day_label = languages[language_code]
    key = request_key(route, trip_budget, trip_days, departure_date, language_code)
    cache_path = app.config['ITINERARY_CACHE_PATH']

    def itinerary_response(plan, cached):
        plan = prepare_itinerary(plan, trip_days, departure_date, language_code)
        text = render_itinerary(plan, language_code, trip_budget)
        return jsonify({**route, 'budget': float(trip_budget), 'currency': 'EUR',
                        'days': trip_days, 'departure_date': departure_date, 'end_date': end_date,
                        'text_itinerary': text, 'itinerary': plan.model_dump(mode='json'),
                        'budget_summary': budget_summary(plan, trip_budget),
                        'cached': cached, 'language': language_code})

    try:
        cached_text = read_itinerary(cache_path, key)
        if cached_text is not None:
            return itinerary_response(Itinerary.model_validate_json(cached_text), True)
        # Fresh tasks prevent one request from retaining another route's prompts/output.
        # Serialize cache misses, then recheck in case another request filled the cache.
        with _crew_lock:
            cached_text = read_itinerary(cache_path, key)
            if cached_text is not None:
                return itinerary_response(Itinerary.model_validate_json(cached_text), True)
            limited = limit_generation()
            if limited is not None:
                return limited
            inputs = {
                **route, 'budget': f'{trip_budget.normalize():f} EUR',
                'duration': f'{trip_days} {"day" if trip_days == 1 else "days"}',
                'departure_date': departure_date or 'Not specified',
                'end_date': end_date or 'Not specified',
                'language': language_name, 'day_label': day_label,
            }
            crew = travel_crew.copy()
            flight_tool = next((tool for agent in crew.agents for tool in agent.tools
                                if tool.name == 'search_flights'), None)
            if flight_tool is not None:
                flight_tool.set_trip(route['origin'], route['destination'], departure_date)

            def validate_itinerary(result):
                plan = prepare_itinerary(parse_crew_itinerary(result), trip_days, departure_date, language_code)
                lookup = flight_tool.result if flight_tool is not None else None
                if lookup and lookup['status'] == 'ok':
                    checked_at = datetime.now(ZoneInfo('Europe/Bucharest')).isoformat(timespec='minutes')
                    plan.flights = FlightResearch(
                        options=lookup['options'],
                        caveat=f'Google Flights via SerpApi · Outbound only · 1 adult · {checked_at}. '
                               'Prices may change before booking. The trip budget still uses estimates.',
                    )
                museum_names = {
                    name
                    for agent in crew.agents
                    for tool in agent.tools
                    if tool.name == 'find_places'
                    for name in tool.returned_names
                }
                return credit_museum_sources(plan, museum_names)

            plan, _ = measured_generation(
                crew, inputs, validate_itinerary,
                app.config['AGENT_METRICS_PATH'], app.logger,
            )
            try:
                save_itinerary(cache_path, key, plan.model_dump_json())
            except Exception:
                # Cache persistence is optional; still return the generated itinerary.
                app.logger.exception('Could not save the completed itinerary to cache')
    except ItineraryValidationError as error:
        app.logger.warning('Itinerary validation failed: %s', error)
        return jsonify(error=f'{error} Please try again.'), 502
    except Exception:
        app.logger.exception('Itinerary generation failed')
        return jsonify(error='Could not create your itinerary. Please try again.'), 502

    return itinerary_response(plan, False)

if __name__ == '__main__':
    # Run the local development server on port 5000.
    app.run(host=os.getenv('HOST', '127.0.0.1'), port=5000, debug=False)
