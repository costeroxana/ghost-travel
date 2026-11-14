import hashlib
import json
import os
import sqlite3
import time
from contextlib import closing

CACHE_TTL_SECONDS = 24 * 60 * 60


def ensure_schema(database):
    database.execute('CREATE TABLE IF NOT EXISTS itineraries '
                     '(request_key TEXT PRIMARY KEY, text_itinerary TEXT NOT NULL, '
                     'created_at REAL NOT NULL DEFAULT 0)')
    columns = {row[1] for row in database.execute('PRAGMA table_info(itineraries)')}
    if 'created_at' not in columns:
        # Existing entries have unknown age, so they expire on the next read.
        database.execute('ALTER TABLE itineraries ADD COLUMN created_at REAL NOT NULL DEFAULT 0')
    if 'trip' not in columns:
        database.execute('ALTER TABLE itineraries ADD COLUMN trip TEXT')


def request_key(route, budget, days, departure_date=None, language='en'):
    # Bump the format version when generation prompts or model settings change.
    settings = [11, bool(os.getenv('LATLNG_API_KEY', '').strip()),
                route['origin'].casefold(), route['destination'].casefold(),
                f'{budget.normalize():f}', days, 'EUR', departure_date, language]
    return hashlib.sha256(json.dumps(settings, ensure_ascii=False).encode('utf-8')).hexdigest()


def read_itinerary(path, key):
    with closing(sqlite3.connect(path, timeout=10)) as database, database:
        ensure_schema(database)
        database.execute('DELETE FROM itineraries WHERE created_at <= ?',
                         (time.time() - CACHE_TTL_SECONDS,))
        row = database.execute('SELECT text_itinerary FROM itineraries WHERE request_key = ?',
                               (key,)).fetchone()
    return row[0] if row else None


def recent_itineraries(path):
    with closing(sqlite3.connect(path, timeout=10)) as database, database:
        ensure_schema(database)
        return database.execute(
            'SELECT request_key, text_itinerary, created_at, trip FROM itineraries '
            'WHERE created_at > ? ORDER BY created_at DESC, request_key LIMIT 30',
            (time.time() - CACHE_TTL_SECONDS,),
        ).fetchall()


def save_itinerary(path, key, text, trip=None):
    with closing(sqlite3.connect(path, timeout=10)) as database, database:
        ensure_schema(database)
        database.execute('INSERT OR REPLACE INTO itineraries '
                         '(request_key, text_itinerary, created_at, trip) VALUES (?, ?, ?, ?)',
                         (key, text, time.time(), json.dumps(trip) if trip is not None else None))
