"""Local execution metrics; stores no prompts, itinerary text or credentials."""

import argparse
import json
import sqlite3
import time
import uuid
from contextlib import closing
from pathlib import Path


def usage_snapshot(crew):
    usage = {}
    for agent in crew.agents:
        llm = agent.llm
        if id(llm) in usage:
            continue
        getter = getattr(llm, 'get_token_usage_summary', None)
        if callable(getter):
            value = getter()
            if hasattr(value, 'model_dump'):
                value = value.model_dump()
            if isinstance(value, dict):
                usage[id(llm)] = {key: count for key, count in value.items()
                                  if isinstance(count, int) and not isinstance(count, bool)}
    return usage


def usage_delta(before, after):
    # Deduplicate shared LLM instances and attribute usage to the executing task.
    if not after:
        return None
    totals = {}
    for identity, values in after.items():
        for key, value in values.items():
            totals[key] = totals.get(key, 0) + max(0, value - before.get(identity, {}).get(key, 0))
    return totals or None


def save_metrics(path, report):
    with closing(sqlite3.connect(path, timeout=5)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created REAL, report TEXT)')
        db.execute('INSERT INTO runs VALUES (?, ?, ?)', (report['id'], time.time(), json.dumps(report)))
        db.execute('DELETE FROM runs WHERE id NOT IN (SELECT id FROM runs ORDER BY created DESC LIMIT 1000)')


def measured_generation(crew, inputs, validate, path, logger, mode='crew'):
    started = time.monotonic()
    report = {'id': uuid.uuid4().hex, 'mode': mode, 'status': 'failed', 'tasks': []}
    completed = set()
    baseline = {}
    previous_callback = crew.task_callback
    try:
        baseline = usage_snapshot(crew)
    except Exception:
        logger.warning('Agent token counters are unavailable')

    def task_finished(output):
        nonlocal baseline
        try:
            task = next(task for task in crew.tasks if task.output is output)
            current = usage_snapshot(crew)
            report['tasks'].append({'name': task.name, 'status': 'completed',
                                    'seconds': task.execution_duration,
                                    'tokens': usage_delta(baseline, current)})
            completed.add(id(task))
            baseline = current
        except Exception:
            logger.warning('Could not collect task metrics')
        if previous_callback:
            previous_callback(output)

    crew.task_callback = task_finished
    try:
        result = crew.kickoff(inputs=inputs)
        plan = validate(result)
        report['status'] = 'completed'
        return plan, report
    except Exception as error:
        report['error_type'] = type(error).__name__
        raise
    finally:
        report['seconds'] = round(time.monotonic() - started, 3)
        try:
            remaining_usage = usage_delta(baseline, usage_snapshot(crew))
            for task in crew.tasks:
                if id(task) not in completed:
                    ran = task.start_time is not None
                    report['tasks'].append({'name': task.name,
                                            'status': 'failed' if ran and task.output is None else ('completed' if ran else 'not_started'),
                                            'seconds': task.execution_duration,
                                            'tokens': remaining_usage if ran else None})
                    if ran:
                        remaining_usage = None
            save_metrics(path, report)
            logger.info('Agent run %s: %s in %.3fs', report['id'], report['status'], report['seconds'])
        except Exception:
            # Observability must not discard a successfully generated itinerary.
            logger.warning('Could not persist agent metrics')
        finally:
            crew.task_callback = previous_callback


def main():
    parser = argparse.ArgumentParser(description='Read local agent metrics; makes no model calls.')
    parser.add_argument('--database', default=str(Path(__file__).with_name('agent_metrics.sqlite3')))
    args = parser.parse_args()
    if not Path(args.database).exists():
        print('No agent runs recorded yet.')
        return
    with closing(sqlite3.connect(args.database)) as db:
        reports = [json.loads(row[0]) for row in db.execute('SELECT report FROM runs ORDER BY created DESC LIMIT 10')]
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    main()
