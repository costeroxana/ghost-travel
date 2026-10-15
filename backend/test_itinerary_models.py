import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from pydantic import ValidationError

from itinerary_models import (Activity, BudgetItem, LocalPlace, Itinerary, LABELS, WEEKDAYS,
                              ItineraryValidationError, parse_crew_itinerary,
                              prepare_itinerary, budget_summary, render_itinerary)


def sample_plan(overview='Test itinerary'):
    return Itinerary.model_validate({
        'overview': overview,
        'flights': {'options': [{'route': 'London to Paris', 'estimate': 'Unverified estimate: 100–200 EUR round-trip.'}],
                    'caveat': 'Verify schedules, routes and prices before booking.'},
        'accommodation': 'Consider a centrally located guesthouse.',
        'days': [{'number': 1, 'date': '2096-02-28', 'title': 'Explore the city',
                  'activities': [{'period': 'afternoon', 'title': 'Walk', 'place': 'City centre',
                                  'details': 'Allow time for arrival.', 'estimated_cost_eur': 0}]}],
        'budget_advice': ['Consider different travel dates; verify costs first.'],
        'budget': [{'kind': 'flights', 'category': 'Flights', 'estimated_cost_eur': None, 'notes': 'Check current fares.'}],
        'practical_tips': ['Check opening hours.'],
    })


def crew_result(overview='Test itinerary', days=3):
    plan = sample_plan(overview)
    plan.days = [plan.days[0].model_copy(deep=True, update={'number': number}) for number in range(1, days + 1)]
    return SimpleNamespace(pydantic=plan)


class ItineraryModelTests(unittest.TestCase):
    def test_cost_schema_requests_numbers_without_decimal_regex(self):
        for model in (LocalPlace, Activity, BudgetItem):
            schema = model.model_json_schema()['properties']['estimated_cost_eur']
            self.assertEqual(schema['anyOf'], [{'type': 'number', 'minimum': 0}, {'type': 'null'}])

    def test_typed_and_raw_crew_outputs_are_supported(self):
        plan = sample_plan()
        self.assertEqual(parse_crew_itinerary(SimpleNamespace(pydantic=plan)), plan)
        self.assertEqual(parse_crew_itinerary(SimpleNamespace(pydantic=None, raw=plan.model_dump_json())), plan)

    def test_invalid_outputs_fail_instead_of_becoming_user_visible_json(self):
        for raw in ('Some Markdown', '{}', sample_plan().model_dump_json().replace('afternoon', 'midnight')):
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                parse_crew_itinerary(raw)
        for amount in (-1, 'NaN', 'Infinity'):
            data = sample_plan().model_dump()
            data['budget'][0]['estimated_cost_eur'] = amount
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                Itinerary.model_validate(data)

    def test_markdown_preserves_localized_day_cards_and_unknown_costs(self):
        for language, labels in LABELS.items():
            text = render_itinerary(sample_plan(), language)
            self.assertIn(f'## {labels[3]} 1 — 2096-02-28 ({WEEKDAYS[language][date(2096, 2, 28).weekday()]}):', text)
            self.assertIn(f'### {labels[7]}', text)
            self.assertIn(f'{labels[9]}: 0.00 EUR', text)
            self.assertIn(f'**Flights**: {labels[10]}', text)
            self.assertIn('Verify schedules, routes and prices before booking.', text)

    def test_unspecified_date_and_model_text_cannot_add_day_sections(self):
        plan = sample_plan('Overview\n\n## Day 99')
        plan.days[0].date = None
        text = render_itinerary(plan, 'en')
        self.assertEqual(sum(line.startswith('## Day ') for line in text.splitlines()), 1)
        self.assertIn('## Day 1: Explore the city', text)

    def test_dates_are_derived_across_leap_day_and_year_boundary(self):
        for start, expected in [('2096-02-28', ['2096-02-28', '2096-02-29', '2096-03-01']),
                                ('2096-12-31', ['2096-12-31', '2097-01-01', '2097-01-02'])]:
            original = crew_result().pydantic
            original.days.reverse()
            plan = prepare_itinerary(original, 3, start)
            self.assertEqual([day.date.isoformat() for day in plan.days], expected)
            self.assertEqual([day.number for day in original.days], [3, 2, 1])
            self.assertTrue(all(day.date is None for day in prepare_itinerary(plan, 3, None).days))
        plan = prepare_itinerary(sample_plan(), 1, '2026-10-29')
        self.assertIn('2026-10-29 (Thursday)', render_itinerary(plan, 'en'))

    def test_missing_extra_or_repeated_days_are_rejected(self):
        for numbers in ([1], [1, 2, 3, 4], [1, 1, 3], [1, 2, 4]):
            plan = crew_result(days=len(numbers)).pydantic
            for day, number in zip(plan.days, numbers):
                day.number = number
            with self.subTest(numbers=numbers), self.assertRaises(ItineraryValidationError):
                prepare_itinerary(plan, 3, None)

    def test_budget_total_uses_rounded_decimal_categories_and_preserves_unknowns(self):
        plan = sample_plan()
        plan.budget = [BudgetItem(kind='flights', category='Flights', estimated_cost_eur=Decimal('100.105'), notes='Estimate'),
                       BudgetItem(kind='food', category='Food', estimated_cost_eur=Decimal('20.105'), notes='Estimate')]
        plan.budget.extend(BudgetItem(kind=kind, category=kind, estimated_cost_eur=0, notes='Estimate') for kind in ('accommodation', 'activities', 'local_transport'))
        plan = prepare_itinerary(plan, 1, None)
        summary = budget_summary(plan, Decimal('120'))
        self.assertEqual(summary['estimated_total_eur'], '120.22')
        self.assertTrue(summary['exceeds_budget'])
        self.assertIn('Estimated total: 120.22 EUR', render_itinerary(plan, 'en', Decimal('120')))
        plan.budget[0].estimated_cost_eur = None
        summary = budget_summary(plan, Decimal('500'))
        self.assertIsNone(summary['estimated_total_eur'])
        self.assertTrue(summary['has_unknown_costs'])
        self.assertEqual(summary['known_estimated_cost_eur'], '20.11')
        self.assertFalse(summary['exceeds_budget'])
        self.assertIn('the full total is unknown', render_itinerary(plan, 'en', Decimal('500')))

    def test_duplicate_budget_categories_are_rejected(self):
        plan = sample_plan()
        plan.budget.append(plan.budget[0].model_copy(update={'category': '  FLIGHTS  '}))
        with self.assertRaises(ItineraryValidationError):
            prepare_itinerary(plan, 1, None)

    def test_missing_core_costs_are_unknown_and_cannot_imply_affordability(self):
        plan = sample_plan()
        plan.budget[0].estimated_cost_eur = Decimal('0')
        prepared = prepare_itinerary(plan, 1, None, 'ro')
        self.assertEqual(len(prepared.budget), 5)
        self.assertIn('Cazare', [item.category for item in prepared.budget])
        self.assertEqual(budget_summary(prepared, Decimal('100'))['status'], 'unknown')
        prepared.budget_advice = []
        self.assertIn('Opțiuni pentru buget', render_itinerary(prepared, 'ro', Decimal('100')))

    def test_over_budget_plan_is_not_repriced_and_has_actionable_advice(self):
        plan = sample_plan()
        plan.budget[0].estimated_cost_eur = Decimal('200')
        plan = prepare_itinerary(plan, 1, None)
        summary = budget_summary(plan, Decimal('50'))
        self.assertEqual(summary['status'], 'over_budget')
        self.assertEqual(summary['known_shortfall_eur'], '150.00')
        self.assertEqual(plan.budget[0].estimated_cost_eur, Decimal('200'))
        self.assertIn('Consider different travel dates', render_itinerary(plan, 'en', Decimal('50')))

    def test_overlapping_budget_kinds_are_rejected_even_with_different_labels(self):
        plan = sample_plan()
        plan.budget.append(BudgetItem(kind='flights', category='Return ticket', estimated_cost_eur=50, notes='Estimate'))
        with self.assertRaises(ItineraryValidationError):
            prepare_itinerary(plan, 1, None)


if __name__ == '__main__':
    unittest.main()
