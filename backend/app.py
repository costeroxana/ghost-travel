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
from destination_photos import destination_photo, destination_photos

# 1. Load environment settings from .env.
load_dotenv()

print("🧠 Initializing Ghost Travel Agent...")

# 2. Define the agents and their roles.

# Agent 1: Flight logistics expert.
flight_hunter = Agent(
    role='Flight Logistics Expert',
    goal='Find the most efficient and cost-effective flight routes.',
    backstory='''You are a master of aviation routing. You know how to analyze flight
    patterns, connection times, and budget airlines to find hidden flight deals
    that normal travelers miss.''',
    verbose=True,
    allow_delegation=False
)

# Agent 2: Local guide.
local_explorer = Agent(
    role='Alternative Local Guide',
    goal='Discover authentic, non-touristy attractions and local culinary spots.',
    backstory='''You hate tourist traps. You spend your time reading local blogs,
    neighborhood forums, and cultural archives to find authentic "hidden gems"
    and incredible local restaurants.''',
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
    Focus on maximizing time at the destination while keeping costs minimal within the overall {budget} budget.''',
    expected_output='A summary of the best estimated flight options including departure/return windows and estimated costs.',
    agent=flight_hunter
)

task_find_local_spots = Task(
    description='''Find 4-5 unique, non-touristy attractions and 3 highly-rated local restaurants in {destination}.
    Select enough options for {duration} and respect the total trip budget of {budget}.
    Trip dates: {departure_date} through {end_date}; consider season and weekday closures.
    Write your response in {language}.
    Avoid standard traps like overpriced central plazas; find spots loved by locals.''',
    expected_output='A curated list of hidden gems, local food spots, and short descriptions of why they are special.',
    agent=local_explorer
)

task_create_itinerary = Task(
    description='''Review the flight options and local spots provided by the other agents.
    Create a highly optimized itinerary covering exactly {duration} for {destination} within the total {budget} budget.
    Treat this as the total trip budget including flights, accommodation, food, and activities.
    Trip dates: {departure_date} through {end_date}. When dates are specified, include
    the calendar date and weekday in each Day N heading. The departure date is Day 1.
    Group activities logically by neighborhood so the traveler doesn't waste time crossing the city.
    Write in {language} using Markdown. Translate all section headings into {language}.
    Start with a brief overview, then use ## headings for
    Flights, Where to stay, each Day N, Budget breakdown, and Practical tips.
    Each day heading must start with {day_label} N (using that exact day label), followed by the date.
    Under each day use translated ### Morning, ### Afternoon, and ### Evening headings, with short bullet points
    for activities, travel time, and estimated costs. Use bold for important place names and costs.
    Keep paragraphs short and put blank lines between sections. Use a bullet list for the budget
    breakdown rather than a wide table. Clearly mark prices and flights as estimates.
    Return only the itinerary Markdown, without wrapping it in a code fence.''',
    expected_output='A readable Markdown itinerary with a short overview, flights, accommodation, separate day headings, morning/afternoon/evening lists, estimated budget breakdown, and practical tips.',
    agent=chief_concierge
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

@app.get('/api/destination-photo')
def get_destination_photo():
    destination_name = ' '.join(request.args.get('destination', '').split())
    if not 2 <= len(destination_name) <= 100:
        return jsonify(error='Enter a destination between 2 and 100 characters.'), 400
    try:
        return jsonify(photo=destination_photo(destination_name))
    except Exception:
        app.logger.warning('Destination photo provider is unavailable', exc_info=True)
        return jsonify(photo=None), 200


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

    def itinerary_response(text, cached):
        return jsonify({**route, 'budget': float(trip_budget), 'currency': 'EUR',
                        'days': trip_days, 'departure_date': departure_date, 'end_date': end_date,
                        'text_itinerary': text, 'cached': cached, 'language': language_code})

    try:
        cached_text = read_itinerary(cache_path, key)
        if cached_text is not None:
            return itinerary_response(cached_text, True)
        # Fresh tasks prevent one request from retaining another route's prompts/output.
        with _crew_lock:
            # A matching request may have completed while this caller waited.
            cached_text = read_itinerary(cache_path, key)
            if cached_text is not None:
                return itinerary_response(cached_text, True)
            limited = limit_generation()
            if limited is not None:
                return limited
            result = travel_crew.copy().kickoff(inputs={
                **route, 'budget': f'{trip_budget.normalize():f} EUR',
                'duration': f'{trip_days} {"day" if trip_days == 1 else "days"}',
                'departure_date': departure_date or 'Not specified',
                'end_date': end_date or 'Not specified',
                'language': language_name, 'day_label': day_label,
            })
            text = str(result).strip()
            if not text:
                raise ValueError('The crew returned an empty itinerary')
            try:
                save_itinerary(cache_path, key, text)
            except Exception:
                app.logger.exception('Could not save the completed itinerary to cache')
    except Exception:
        app.logger.exception('Itinerary generation failed')
        return jsonify(error='Could not create your itinerary. Please try again.'), 502

    return itinerary_response(text, False)

if __name__ == '__main__':
    # Run the local development server on port 5000.
    app.run(host=os.getenv('HOST', '127.0.0.1'), port=5000, debug=False)
