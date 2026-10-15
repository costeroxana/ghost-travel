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
from crewai import Agent, Task, Crew, Process
from itinerary_cache import read_itinerary, request_key, save_itinerary
from destination_photos import destination_photos
from agent_metrics import measured_generation
from itinerary_models import (
    FlightResearch, LocalResearch, Itinerary, ItineraryValidationError,
    parse_crew_itinerary, prepare_itinerary, render_itinerary, budget_summary,
)

# 1. Load environment settings from .env.
load_dotenv()

print("🧠 Initializing Ghost Travel Agent...")

# 2. Define the agents and their roles.

# Agent 1: Flight logistics expert.
flight_hunter = Agent(
    role='Flight Logistics Expert',
    goal='Suggest plausible flight routes and clearly labeled planning estimates without claiming live verification.',
    backstory='''You advise travelers on airports, routing, and approximate travel budgets.
    You have no live flight-search or booking access. You distinguish general routing
    advice from verified schedules, fares, and availability, and never invent booking details.''',
    verbose=True,
    allow_delegation=False
)

# Agent 2: Local guide.
local_explorer = Agent(
    role='Alternative Local Guide',
    goal='Discover authentic, non-touristy attractions and local culinary spots.',
    backstory='''You suggest local places from general knowledge. You have no live search
    access, so ratings, opening hours, availability and prices must be verified.
    You distinguish suggestions from verified recommendations.''',
    verbose=True,
    allow_delegation=False
)

# Agent 3: Itinerary coordinator.
chief_concierge = Agent(
    role='Chief Travel Coordinator',
    goal='Assemble flights and local spots into a perfectly timed, budget-friendly daily itinerary.',
    backstory='''You are a master of logistics and time management. You take flight data
    and attraction lists, check the traveler\'s budget, and structure a realistic
    day-by-day plan ensuring locations are geographically close to minimize travel time.''',
    verbose=True,
    allow_delegation=True # This agent can ask the other agents for clarification.
)


# 3. Define the tasks for each agent.

# Default trip settings for clients that do not specify a route.
destination = "Rome, Italy"
origin = "Bucharest, Romania"
budget = "300 EUR"
duration = "3 days (Weekend)"

task_find_flights = Task(
    description='''Analyze potential flight options from {origin} to {destination} for a {duration} trip.
    Departure date: {departure_date}. Last trip day: {end_date}.
    Write your response in {language}.
    You have no live flight-search data. Suggest relevant airports and plausible routes,
    explicitly labeling route availability as unverified for the requested dates.
    Do not invent flight numbers, exact departure or arrival times, bookable fares,
    seat availability, or claims that an airline operates a route on these dates.
    Where useful, provide broad estimated price and journey-time ranges, explaining
    whether prices are per person and round-trip or one-way. If uncertain, say so.
    Preferred travel windows are planning preferences, not actual flight schedules.
    Tell the traveler to verify routes, schedules, and current prices before booking.
    Focus on maximizing time at the destination while keeping costs minimal within the overall {budget} budget.''',
    expected_output='Potential airports and routes with unverified availability, broad labeled cost and travel-time estimates where supportable, and a reminder to verify options before booking; no invented flight numbers or exact schedules.',
    agent=flight_hunter,
    output_pydantic=FlightResearch,
    name='flight_research',
)

task_find_local_spots = Task(
    description='''Suggest 4-5 interesting attractions and 3 local restaurants in {destination}.
    Select enough options for {duration} and respect the total trip budget of {budget}.
    Trip dates: {departure_date} through {end_date}; consider season and weekday closures.
    Write your response in {language}.
    Do not invent ratings, current opening hours, or claims of live research.
    Label prices and closure information as unverified.
    Avoid standard traps like overpriced central plazas; find spots loved by locals.''',
    expected_output='A curated list of hidden gems, local food spots, and short descriptions of why they are special.',
    agent=local_explorer,
    output_pydantic=LocalResearch,
    name='local_research',
)

task_create_itinerary = Task(
    description='''Review the flight options and local spots provided by the other agents.
    Create an itinerary covering exactly {duration} for {destination}, assessing the requested total {budget} budget honestly.
    Treat this as the total trip budget including flights, accommodation, food, and activities.
    Flight suggestions are unverified planning estimates, not live search results.
    Preserve that distinction in the Flights section and label any flight costs in the
    budget breakdown as estimates. Do not add flight numbers, exact flight times,
    confirmed airline routes, availability, or claims of bookable prices.
    Keep arrival-day and return-day activities flexible because flight times are unknown;
    explicitly state any arrival/departure assumptions rather than presenting them as facts.
    Include a reminder in {language} to verify routes, schedules, and prices before booking.
    Trip dates: {departure_date} through {end_date}. When dates are specified, include
    the calendar date in each day object. The departure date is Day 1.
    Group activities logically by neighborhood so the traveler doesn't waste time crossing the city.
    Return structured data matching the Itinerary schema, not Markdown or code fences.
    Write all user-facing text in {language}; keep schema keys and period enum values unchanged.
    Supply an overview, flight options and their verification caveat, accommodation advice,
    numbered days with ISO dates (null if unspecified), and morning/afternoon/evening activities.
    Each activity needs a title, place, details, and estimated EUR cost (null if unknown).
    Supply total-trip budget categories with estimated numeric EUR amounts (null if unknown),
    using distinct, non-overlapping categories. Include flights, accommodation, food,
    activities and local transport, marking any unknown amounts as null. Do not include
    total or subtotal rows; Python calculates the sum. Never claim an unknown cost is free.
    Use each budget kind at most once; do not overlap categories or include totals.
    Do not lower estimates to force the trip within budget. When funds appear insufficient,
    explain the limitation and suggest practical changes (dates, fewer nights, closer destination)
    in budget_advice without claiming verified savings. When costs are unknown, state that
    affordability cannot be confirmed. Do not promise that the trip fits the budget.
    Include explanatory budget notes and practical tips. Do not put weekday names in day titles.
    Keep text concise. Never use zero as a substitute for an unknown cost.''',
    expected_output='A structured Itinerary object containing localized travel advice, individual days and activities, estimated numeric EUR costs or null, and explicit flight uncertainty.',
    agent=chief_concierge,
    output_pydantic=Itinerary,
    name='itinerary_coordinator',
    context=[task_find_flights, task_find_local_spots],
)


# 4. Assemble the crew.
travel_crew = Crew(
    agents=[flight_hunter, local_explorer, chief_concierge],
    tasks=[task_find_flights, task_find_local_spots, task_create_itinerary],
    process=Process.sequential, # Run the tasks sequentially.
    verbose=True
)

# Optional standalone generation example.
# print("🚀 The agents have started working together. Please wait.")
# result = travel_crew.kickoff()

# print("\n#############################################")
# print("🎯 YOUR FINAL ITINERARY FROM GHOST AGENT:")
# print("#############################################\n")
# print(result)


# 5. Expose the backend API for the React Native app.
app = Flask(__name__)
CORS(app) # Allow cross-origin requests from the mobile and web app.
app.config['AGENT_METRICS_PATH'] = os.path.join(os.path.dirname(__file__), 'agent_metrics.sqlite3')
app.config['ITINERARY_CACHE_PATH'] = os.path.join(os.path.dirname(__file__), 'itinerary_cache.sqlite3')

# Shared across callers so changing IP addresses cannot bypass the cost limit.
_request_times = deque()
_rate_limit_lock = Lock()
_crew_lock = Lock()
_rate_limit_requests = 5
_rate_limit_window = 60


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
        with _crew_lock:
            # A matching request may have completed while this caller waited.
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
            plan, _ = measured_generation(
                travel_crew.copy(), inputs,
                lambda result: prepare_itinerary(parse_crew_itinerary(result), trip_days, departure_date, language_code),
                app.config['AGENT_METRICS_PATH'], app.logger,
            )
            try:
                save_itinerary(cache_path, key, plan.model_dump_json())
            except Exception:
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
