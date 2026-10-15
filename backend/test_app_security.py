import contextlib
import io
import runpy
import sys
import unittest
import tempfile
import time
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from test_itinerary_models import crew_result


class AppSecurityTests(unittest.TestCase):
    def setUp(self):
        stdout_patch = patch('sys.stdout', new=io.StringIO())
        stdout_patch.start()
        self.addCleanup(stdout_patch.stop)
        # Load the real routes without initializing providers or making LLM calls.
        crewai = SimpleNamespace(
            Agent=MagicMock(), Task=MagicMock(), Crew=MagicMock(),
            Process=SimpleNamespace(sequential='sequential'),
        )
        with patch.dict(sys.modules, {'crewai': crewai}), contextlib.redirect_stdout(io.StringIO()):
            self.module = runpy.run_path(str(Path(__file__).with_name('app.py')))
        self.app = self.module['app']
        cache_directory = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(cache_directory.cleanup)
        self.app.config['ITINERARY_CACHE_PATH'] = str(Path(cache_directory.name) / 'cache.sqlite3')
        self.app.config['AGENT_METRICS_PATH'] = str(Path(cache_directory.name) / 'metrics.sqlite3')
        self.client = self.app.test_client()
        self.crew = self.module['travel_crew'].copy.return_value
        self.crew.kickoff.side_effect = lambda inputs: crew_result(days=int(inputs['duration'].split()[0]))

    def test_gallery_endpoint_still_returns_photos(self):
        gallery = [{'url': 'https://example.com/rome.jpg', 'title': 'Rome'}]
        with patch.dict(self.app.view_functions['get_destination_photos'].__globals__,
                        {'destination_photos': MagicMock(return_value=gallery)}):
            response = self.client.get('/api/destination-photos?destination=Rome')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'photos': gallery})
        self.crew.kickoff.assert_not_called()

    def test_request_without_key_returns_itinerary(self):
        response = self.client.get('/api/itinerary')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Test itinerary', response.json['text_itinerary'])
        self.crew.kickoff.assert_called_once()

    def test_structured_itinerary_is_preserved_in_cache_and_response(self):
        payload = {'origin': 'London', 'destination': 'Paris'}
        first = self.client.post('/api/itinerary', json=payload)
        second = self.client.post('/api/itinerary', json=payload)
        self.assertEqual(first.json['itinerary']['days'][0]['activities'][0]['period'], 'afternoon')
        self.assertIsNone(first.json['itinerary']['budget'][0]['estimated_cost_eur'])
        self.assertEqual(first.json['itinerary'], second.json['itinerary'])
        self.assertEqual(first.json['text_itinerary'], second.json['text_itinerary'])
        self.assertTrue(second.json['cached'])
        self.crew.kickoff.assert_called_once()
        with sqlite3.connect(self.app.config['AGENT_METRICS_PATH']) as database:
            self.assertEqual(database.execute('SELECT COUNT(*) FROM runs').fetchone()[0], 1)
        database.close()

    def test_invalid_structured_generation_is_not_cached(self):
        self.crew.kickoff.side_effect = [SimpleNamespace(pydantic=None, raw='Invalid output'), crew_result()]
        payload = {'origin': 'London', 'destination': 'Paris'}
        with patch.object(self.app.logger, 'exception'):
            self.assertEqual(self.client.post('/api/itinerary', json=payload).status_code, 502)
        response = self.client.post('/api/itinerary', json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json['cached'])

    def test_incomplete_itinerary_is_rejected_without_caching(self):
        self.crew.kickoff.side_effect = [crew_result(days=1), crew_result(days=3)]
        payload = {'origin': 'London', 'destination': 'Paris', 'days': 3}
        with patch.object(self.app.logger, 'warning'):
            invalid = self.client.post('/api/itinerary', json=payload)
        self.assertEqual(invalid.status_code, 502)
        self.assertIn('wrong number of days', invalid.json['error'])
        valid = self.client.post('/api/itinerary', json=payload)
        self.assertEqual(valid.status_code, 200)
        self.assertFalse(valid.json['cached'])

    def test_response_uses_requested_dates_and_computed_budget(self):
        payload = {'origin': 'London', 'destination': 'Paris', 'days': 3, 'departure_date': '2096-02-28'}
        response = self.client.post('/api/itinerary', json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([day['date'] for day in response.json['itinerary']['days']],
                         ['2096-02-28', '2096-02-29', '2096-03-01'])
        self.assertIsNone(response.json['budget_summary']['estimated_total_eur'])
        self.assertTrue(response.json['budget_summary']['has_unknown_costs'])
        cached = self.client.post('/api/itinerary', json=payload)
        self.assertEqual(cached.json['budget_summary'], response.json['budget_summary'])
        self.assertTrue(cached.json['cached'])

    def test_limit_is_shared_and_expires(self):
        headers = {}
        with patch('time.monotonic', return_value=100):
            for index in range(5):
                response = self.client.get(f'/api/itinerary?destination=City{index}', headers=headers,
                                           environ_overrides={'REMOTE_ADDR': f'192.0.2.{index}'})
                self.assertEqual(response.status_code, 200)
                self.assertIn('Test itinerary', response.json['text_itinerary'])
            response = self.client.get('/api/itinerary?destination=NewCity', headers=headers)
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers['Retry-After'], '60')
        self.assertEqual(self.crew.kickoff.call_count, 5)
        with patch('time.monotonic', return_value=160):
            self.assertEqual(self.client.get('/api/itinerary?destination=NewCity', headers=headers).status_code, 200)

    def test_identical_requests_reuse_saved_result(self):
        payload = {'origin': 'London', 'destination': 'Paris', 'budget': '300.00', 'days': 3}
        first = self.client.post('/api/itinerary', json=payload)
        self.assertFalse(first.json['cached'])
        self.module['_request_times'].extend([time.monotonic()] * 5)
        self.crew.kickoff.reset_mock()
        second = self.client.post('/api/itinerary', json={
            **payload, 'origin': '  LONDON ', 'destination': 'paris', 'budget': 300,
        })
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json['cached'])
        self.assertEqual(second.json['text_itinerary'], first.json['text_itinerary'])
        self.crew.kickoff.assert_not_called()

    def test_saved_result_survives_app_reload(self):
        payload = {'origin': 'London', 'destination': 'Paris'}
        self.client.post('/api/itinerary', json=payload)
        crewai = SimpleNamespace(Agent=MagicMock(), Task=MagicMock(), Crew=MagicMock(),
                                Process=SimpleNamespace(sequential='sequential'))
        with patch.dict(sys.modules, {'crewai': crewai}):
            reloaded = runpy.run_path(str(Path(__file__).with_name('app.py')))
        reloaded['app'].config['ITINERARY_CACHE_PATH'] = self.app.config['ITINERARY_CACHE_PATH']
        response = reloaded['app'].test_client().post('/api/itinerary', json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['cached'])
        crewai.Crew.return_value.copy.assert_not_called()

    def test_cache_expires_at_24_hours_and_refreshes(self):
        payload = {'origin': 'London', 'destination': 'Paris'}
        self.crew.kickoff.side_effect = [crew_result('Original itinerary'), crew_result('Updated itinerary')]
        with patch('itinerary_cache.time.time', return_value=100000):
            first = self.client.post('/api/itinerary', json=payload)
        with patch('itinerary_cache.time.time', return_value=186399):
            before_expiry = self.client.post('/api/itinerary', json=payload)
        self.assertTrue(before_expiry.json['cached'])
        self.assertEqual(before_expiry.json['text_itinerary'], first.json['text_itinerary'])
        with patch('itinerary_cache.time.time', return_value=186400):
            expired = self.client.post('/api/itinerary', json=payload)
        self.assertFalse(expired.json['cached'])
        self.assertIn('Updated itinerary', expired.json['text_itinerary'])
        with patch('itinerary_cache.time.time', return_value=186401):
            refreshed = self.client.post('/api/itinerary', json=payload)
        self.assertTrue(refreshed.json['cached'])
        self.assertIn('Updated itinerary', refreshed.json['text_itinerary'])
        self.assertEqual(self.crew.kickoff.call_count, 2)

    def test_legacy_cache_migrates_and_expires_unknown_age(self):
        path = self.app.config['ITINERARY_CACHE_PATH']
        database = sqlite3.connect(path)
        try:
            database.execute('CREATE TABLE itineraries '
                             '(request_key TEXT PRIMARY KEY, text_itinerary TEXT NOT NULL)')
            database.execute('INSERT INTO itineraries VALUES (?, ?)', ('legacy', 'Old itinerary'))
            database.commit()
        finally:
            database.close()
        response = self.client.post('/api/itinerary', json={'origin': 'London', 'destination': 'Paris'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json['cached'])
        database = sqlite3.connect(path)
        try:
            self.assertIsNone(database.execute('SELECT 1 FROM itineraries WHERE request_key = ?', ('legacy',)).fetchone())
        finally:
            database.close()

    def test_changed_trip_settings_have_separate_cache_entries(self):
        payload = {'origin': 'London', 'destination': 'Paris', 'budget': 300, 'days': 3}
        for changes in ({}, {'origin': 'Berlin'}, {'destination': 'Rome'}, {'budget': 400}, {'days': 4}):
            response = self.client.post('/api/itinerary', json={**payload, **changes})
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json['cached'])
        self.assertEqual(self.crew.kickoff.call_count, 5)

    def test_failed_generation_is_not_cached(self):
        payload = {'origin': 'London', 'destination': 'Paris'}
        self.crew.kickoff.side_effect = [RuntimeError('Unavailable'), crew_result('Successful itinerary')]
        with patch.object(self.app.logger, 'exception'):
            self.assertEqual(self.client.post('/api/itinerary', json=payload).status_code, 502)
        response = self.client.post('/api/itinerary', json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json['cached'])
        self.assertEqual(self.crew.kickoff.call_count, 2)

    def test_simultaneous_identical_requests_generate_once(self):
        started, release = Event(), Event()

        def generate(**kwargs):
            started.set()
            if not release.wait(3):
                raise RuntimeError('Test did not release generation')
            return crew_result('Shared itinerary')

        self.crew.kickoff.side_effect = generate

        def make_request():
            with self.app.test_client() as client:
                return client.post('/api/itinerary', json={'origin': 'London', 'destination': 'Paris'})

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(make_request)
            self.assertTrue(started.wait(3))
            second = executor.submit(make_request)
            release.set()
            responses = [first.result(timeout=5), second.result(timeout=5)]
        self.assertEqual([response.status_code for response in responses], [200, 200])
        self.assertEqual(sum(response.json['cached'] for response in responses), 1)
        self.crew.kickoff.assert_called_once()

    def test_preflight_does_not_run_crew(self):
        self.assertEqual(self.client.options('/api/itinerary').status_code, 200)
        self.crew.kickoff.assert_not_called()

    def test_selected_route_reaches_crew_and_response(self):
        for origin, destination in [('Cluj-Napoca, Romania', 'Paris, France'), ('London', 'Tokyo')]:
            response = self.client.post('/api/itinerary', json={
                'origin': f'  {origin}  ', 'destination': destination,
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['origin'], origin)
            self.assertEqual(response.json['destination'], destination)
            self.crew.kickoff.assert_called_with(inputs={
                'origin': origin, 'destination': destination,
                'budget': '300 EUR', 'duration': '3 days',
                'departure_date': 'Not specified', 'end_date': 'Not specified',
                'language': 'English', 'day_label': 'Day',
            })
        self.assertEqual(self.module['travel_crew'].copy.call_count, 2)

    def test_invalid_routes_never_run_crew(self):
        for payload in ({}, {'origin': [], 'destination': 'Paris'},
                        {'origin': ' ', 'destination': 'Paris'},
                        {'origin': 'Rome', 'destination': ' rome '},
                        {'origin': 'A' * 101, 'destination': 'Paris'}):
            with self.subTest(payload=payload):
                self.module['_request_times'].clear()
                self.assertEqual(self.client.post('/api/itinerary', json=payload).status_code, 400)
        self.crew.kickoff.assert_not_called()

    def test_custom_budget_and_duration_reach_agents(self):
        for amount, days, expected_amount in [('1250.50', 7, '1250.5'), (100, 1, '100')]:
            response = self.client.post('/api/itinerary', json={
                'origin': 'London', 'destination': 'Paris', 'budget': amount, 'days': days,
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['budget'], float(amount))
            self.assertEqual(response.json['days'], days)
            self.crew.kickoff.assert_called_with(inputs={
                'origin': 'London', 'destination': 'Paris', 'budget': f'{expected_amount} EUR',
                'duration': f'{days} {"day" if days == 1 else "days"}',
                'departure_date': 'Not specified', 'end_date': 'Not specified',
                'language': 'English', 'day_label': 'Day',
            })

    def test_invalid_budget_and_days_do_not_run_agents(self):
        for field, values in [('budget', [0, -1, True, None, 'NaN', '1.234', 100001]),
                              ('days', [0, -1, True, None, 1.5, 31, 'seven'])]:
            for value in values:
                with self.subTest(field=field, value=value):
                    self.module['_request_times'].clear()
                    response = self.client.post('/api/itinerary', json={
                        'origin': 'London', 'destination': 'Paris', field: value,
                    })
                    self.assertEqual(response.status_code, 400)
        self.crew.kickoff.assert_not_called()

    def test_departure_date_drives_trip_dates_and_cache(self):
        payload = {'origin': 'London', 'destination': 'Paris', 'days': 3,
                   'departure_date': '2096-02-28'}
        response = self.client.post('/api/itinerary', json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['end_date'], '2096-03-01')
        inputs = self.crew.kickoff.call_args.kwargs['inputs']
        self.assertEqual(inputs['departure_date'], '2096-02-28')
        self.assertEqual(inputs['end_date'], '2096-03-01')
        self.assertTrue(self.client.post('/api/itinerary', json=payload).json['cached'])
        changed = self.client.post('/api/itinerary', json={**payload, 'departure_date': '2096-02-29'})
        self.assertFalse(changed.json['cached'])
        self.assertEqual(self.crew.kickoff.call_count, 2)

    def test_invalid_departure_dates_do_not_run_agents(self):
        for value in ['2020-01-01', '2097-02-29', 'not-a-date', '2096-2-3', '', True, '9999-12-31']:
            with self.subTest(value=value):
                response = self.client.post('/api/itinerary', json={
                    'origin': 'London', 'destination': 'Paris', 'departure_date': value,
                })
                self.assertEqual(response.status_code, 400)
        self.crew.kickoff.assert_not_called()

    def test_each_language_reaches_agents_and_has_its_own_cache(self):
        payload = {'origin': 'London', 'destination': 'Paris'}
        for code, name, label in [('en', 'English', 'Day'), ('ro', 'Romanian', 'Ziua'),
                                  ('es', 'Spanish', 'Día'), ('fr', 'French', 'Jour'),
                                  ('de', 'German', 'Tag'), ('it', 'Italian', 'Giorno')]:
            self.module['_request_times'].clear()
            response = self.client.post('/api/itinerary', json={**payload, 'language': code})
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json['cached'])
            self.assertEqual(response.json['language'], code)
            inputs = self.crew.kickoff.call_args.kwargs['inputs']
            self.assertEqual(inputs['language'], name)
            self.assertEqual(inputs['day_label'], label)
            self.assertTrue(self.client.post('/api/itinerary', json={**payload, 'language': code}).json['cached'])
        self.assertEqual(self.crew.kickoff.call_count, 6)

    def test_unsupported_language_does_not_run_agents(self):
        for language in ('xx', [], None):
            response = self.client.post('/api/itinerary', json={
                'origin': 'London', 'destination': 'Paris', 'language': language,
            })
            self.assertEqual(response.status_code, 400)
        self.crew.kickoff.assert_not_called()

    def test_provider_failure_returns_json_error(self):
        self.crew.kickoff.side_effect = RuntimeError('Provider unavailable')
        with patch.object(self.app.logger, 'exception'):
            response = self.client.post('/api/itinerary', json={'origin': 'London', 'destination': 'Paris'})
        self.assertEqual(response.status_code, 502)
        self.assertIn('error', response.json)

    def test_direct_server_start_disables_debug_and_defaults_to_loopback(self):
        with patch.dict(sys.modules, {'crewai': SimpleNamespace(
            Agent=MagicMock(), Task=MagicMock(), Crew=MagicMock(),
            Process=SimpleNamespace(sequential='sequential'),
        )}), patch('flask.Flask.run') as run, patch('dotenv.load_dotenv'), \
                patch.dict('os.environ', {'HOST': '127.0.0.1'}), \
                contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(str(Path(__file__).with_name('app.py')), run_name='__main__')
        run.assert_called_once_with(host='127.0.0.1', port=5000, debug=False)


if __name__ == '__main__':
    unittest.main()
