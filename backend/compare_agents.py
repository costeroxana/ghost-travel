"""Explicit, paid-call comparison of the existing crew and a single coordinator."""

import argparse
import json
import logging
import tempfile
from pathlib import Path

from agent_metrics import measured_generation
from itinerary_models import budget_summary, parse_crew_itinerary, prepare_itinerary
from decimal import Decimal


def compare(crew, inputs, days, departure_date, budget, path, logger):
    reports = []
    for mode in ('crew', 'single'):
        candidate = crew.copy()
        if mode == 'single':
            final = candidate.tasks[-1]
            final.context = []
            final.description = final.description.replace(
                'Review the flight options and local spots provided by the other agents.',
                'Independently suggest flights and local places from general knowledge; no live research tools are available.')
            final.agent.allow_delegation = False
            candidate.tasks = [final]
            candidate.agents = [final.agent]
        plan, report = measured_generation(
            candidate, inputs,
            lambda result: prepare_itinerary(parse_crew_itinerary(result), days, departure_date),
            path, logger, mode,
        )
        reports.append({**report, 'days': len(plan.days),
                        'activities': sum(len(day.activities) for day in plan.days),
                        'budget': budget_summary(plan, budget)})
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Required: authorizes model calls using your configured API account.')
    parser.add_argument('--output', default='agent_comparison.json')
    args = parser.parse_args()
    if not args.live:
        parser.error('Use --live to explicitly run this comparison with paid model calls.')
    import app
    inputs = {'origin': 'London', 'destination': 'Paris', 'budget': '500 EUR', 'duration': '2 days',
              'departure_date': 'Not specified', 'end_date': 'Not specified', 'language': 'English', 'day_label': 'Day'}
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
        reports = compare(app.travel_crew, inputs, 2, None, Decimal('500'),
                          str(Path(directory) / 'metrics.sqlite3'), logging.getLogger(__name__))
    Path(args.output).write_text(json.dumps(reports, indent=2), encoding='utf8')
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    main()
