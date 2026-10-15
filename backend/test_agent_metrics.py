import json
import logging
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent_metrics import measured_generation


class FakeCrew:
    def __init__(self, fail=False):
        self.fail = fail
        self.count = 20
        llm = SimpleNamespace(get_token_usage_summary=lambda: {'total_tokens': self.count})
        self.agents = [SimpleNamespace(llm=llm), SimpleNamespace(llm=llm)]
        self.tasks = [SimpleNamespace(name=name, output=None, start_time=None, execution_duration=None)
                      for name in ('flights', 'places')]
        self.task_callback = None

    def kickoff(self, inputs):
        for task in self.tasks:
            task.start_time = 1
            self.count += 10
            if self.fail:
                raise RuntimeError('Provider failed')
            task.output = object()
            task.execution_duration = 1.5
            self.task_callback(task.output)
        return 'generated'


class AgentMetricTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(temporary.cleanup)
        self.path = str(Path(temporary.name) / 'metrics.sqlite3')
        self.logger = logging.getLogger(__name__)

    def report(self):
        with closing(sqlite3.connect(self.path)) as db:
            return json.loads(db.execute('SELECT report FROM runs').fetchone()[0])

    def test_shared_counters_are_deduplicated_and_prior_usage_excluded(self):
        crew = FakeCrew()
        result, report = measured_generation(crew, {'secret': 'must not persist'}, lambda value: value, self.path, self.logger)
        self.assertEqual(result, 'generated')
        self.assertEqual(report['status'], 'completed')
        self.assertEqual([task['tokens']['total_tokens'] for task in self.report()['tasks']], [10, 10])
        self.assertNotIn('secret', json.dumps(self.report()))
        self.assertIsNone(crew.task_callback)

    def test_failures_and_tasks_not_started_are_recorded(self):
        with self.assertRaises(RuntimeError):
            measured_generation(FakeCrew(fail=True), {}, lambda value: value, self.path, self.logger)
        report = self.report()
        self.assertEqual(report['status'], 'failed')
        self.assertEqual([task['status'] for task in report['tasks']], ['failed', 'not_started'])
        self.assertEqual(report['tasks'][0]['tokens']['total_tokens'], 10)

    def test_validation_failure_is_recorded_and_storage_failure_does_not_break_success(self):
        def invalid(value):
            raise ValueError('Invalid itinerary')
        with self.assertRaises(ValueError):
            measured_generation(FakeCrew(), {}, invalid, self.path, self.logger)
        self.assertEqual(self.report()['error_type'], 'ValueError')
        with patch('agent_metrics.save_metrics', side_effect=OSError), patch.object(self.logger, 'warning'):
            result, _ = measured_generation(FakeCrew(), {}, lambda value: value, self.path, self.logger)
        self.assertEqual(result, 'generated')
