"""Typed agent results and the Markdown adapter used by existing clients."""

from datetime import date as CalendarDate, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema


# Pydantic's default Decimal schema includes a regex-string alternative that
# fails during constrained generation with the configured model. Request JSON
# numbers from the provider while retaining Decimal precision and validation.
EstimatedCost = Annotated[
    Decimal, Field(ge=0), WithJsonSchema({'type': 'number', 'minimum': 0}, mode='validation'),
]


class OutputModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class FlightOption(OutputModel):
    route: str = Field(min_length=1, description='Potential airports/routing; availability is unverified.')
    estimate: str = Field(min_length=1, description='Broad cost and journey-time estimates, with units and uncertainty.')


class FlightResearch(OutputModel):
    options: list[FlightOption]
    caveat: str = Field(min_length=1, description='Localized reminder that routes, schedules and prices require verification.')


class LocalPlace(OutputModel):
    name: str = Field(min_length=1)
    kind: Literal['attraction', 'restaurant']
    area: str
    description: str
    estimated_cost_eur: EstimatedCost | None = Field(description='Estimated per-person cost in EUR, or null if unknown.')


class LocalResearch(OutputModel):
    places: list[LocalPlace]
    caveats: list[str]


class Activity(OutputModel):
    period: Literal['morning', 'afternoon', 'evening']
    title: str = Field(min_length=1)
    place: str
    details: str = Field(min_length=1, description='Localized activity and travel-time advice; label uncertain estimates.')
    estimated_cost_eur: EstimatedCost | None = Field(description='Estimated activity cost in EUR, or null if unknown.')


class ItineraryDay(OutputModel):
    number: int = Field(ge=1, le=30)
    date: CalendarDate | None = Field(description='ISO calendar date, or null when no departure date was supplied.')
    title: str = Field(min_length=1, description='Localized short day description, without a day number or weekday.')
    activities: list[Activity] = Field(min_length=1)


class BudgetItem(OutputModel):
    kind: Literal['flights', 'accommodation', 'food', 'activities', 'local_transport', 'other']
    category: str = Field(min_length=1, description='Localized budget category, e.g. flights or accommodation.')
    estimated_cost_eur: EstimatedCost | None = Field(description='Total estimated category cost for the whole trip, or null if unknown.')
    notes: str = Field(description='Localized assumptions and uncertainty; never imply a confirmed quote.')


class Itinerary(OutputModel):
    overview: str = Field(min_length=1)
    flights: FlightResearch
    accommodation: str = Field(min_length=1)
    days: list[ItineraryDay] = Field(min_length=1, max_length=30)
    budget: list[BudgetItem] = Field(min_length=1)
    practical_tips: list[str] = Field(min_length=1)
    budget_advice: list[str] = Field(description='Localized practical alternatives when costs exceed the budget or cannot be confirmed. Never invent cheaper prices.')


class ItineraryValidationError(ValueError):
    """Generated content does not match the requested trip."""


def prepare_itinerary(plan, requested_days, departure_date, language='en'):
    """Check content completeness, then derive dates from trusted request inputs."""
    if len(plan.days) != requested_days:
        raise ItineraryValidationError('The generated itinerary has the wrong number of days.')
    if sorted(day.number for day in plan.days) != list(range(1, requested_days + 1)):
        raise ItineraryValidationError('The generated itinerary has missing or repeated day numbers.')
    plan = plan.model_copy(deep=True)
    plan.days.sort(key=lambda day: day.number)
    departure = CalendarDate.fromisoformat(departure_date) if departure_date else None
    for day in plan.days:
        day.date = departure + timedelta(days=day.number - 1) if departure else None
    categories = [inline(item.category).casefold() for item in plan.budget]
    if len(set(categories)) != len(categories):
        raise ItineraryValidationError('The generated budget has repeated categories.')
    kinds = [item.kind for item in plan.budget]
    if len(set(kinds)) != len(kinds):
        raise ItineraryValidationError('The generated budget has overlapping categories.')
    for kind, label in zip(CORE_COSTS, COST_LABELS[language]):
        if kind not in kinds:
            plan.budget.append(BudgetItem(kind=kind, category=label, estimated_cost_eur=None, notes=LABELS[language][10]))
    # Round individual displayed amounts first so the displayed sum reconciles.
    for cost in [*plan.budget, *(activity for day in plan.days for activity in day.activities)]:
        if cost.estimated_cost_eur is not None:
            cost.estimated_cost_eur = cost.estimated_cost_eur.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return plan


def budget_summary(plan, requested_budget):
    amounts = [item.estimated_cost_eur for item in plan.budget]
    known = sum((amount for amount in amounts if amount is not None), Decimal('0.00'))
    complete = all(amount is not None for amount in amounts) and set(CORE_COSTS).issubset(item.kind for item in plan.budget)
    return {
        'known_estimated_cost_eur': f'{known:.2f}',
        'estimated_total_eur': f'{known:.2f}' if complete else None,
        'has_unknown_costs': not complete,
        'exceeds_budget': known > requested_budget,
        'status': 'over_budget' if known > requested_budget else ('unknown' if not complete else 'within_estimate'),
        'known_shortfall_eur': f'{max(Decimal(0), known - requested_budget):.2f}',
    }


CORE_COSTS = ('flights', 'accommodation', 'food', 'activities', 'local_transport')
COST_LABELS = {
    'en': ('Flights', 'Accommodation', 'Food', 'Activities', 'Local transport'),
    'ro': ('Zboruri', 'Cazare', 'Mâncare', 'Activități', 'Transport local'),
    'es': ('Vuelos', 'Alojamiento', 'Comida', 'Actividades', 'Transporte local'),
    'fr': ('Vols', 'Hébergement', 'Repas', 'Activités', 'Transports locaux'),
    'de': ('Flüge', 'Unterkunft', 'Essen', 'Aktivitäten', 'Nahverkehr'),
    'it': ('Voli', 'Alloggio', 'Pasti', 'Attività', 'Trasporti locali'),
}
ADVICE_LABELS = {
    'en': ('Budget options', 'Verify missing costs before booking. Consider fewer nights, different dates, or a closer destination; savings are not guaranteed.'),
    'ro': ('Opțiuni pentru buget', 'Verifică sumele necunoscute înainte de rezervare. Ia în calcul mai puține nopți, alte date sau o destinație mai apropiată; economiile nu sunt garantate.'),
    'es': ('Opciones de presupuesto', 'Verifica los costes desconocidos antes de reservar. Considera menos noches, otras fechas o un destino más cercano; el ahorro no está garantizado.'),
    'fr': ('Options de budget', 'Vérifiez les coûts inconnus avant de réserver. Envisagez moins de nuits, d’autres dates ou une destination plus proche ; les économies ne sont pas garanties.'),
    'de': ('Budgetoptionen', 'Prüfe unbekannte Kosten vor der Buchung. Erwäge weniger Nächte, andere Termine oder ein näheres Ziel; Einsparungen sind nicht garantiert.'),
    'it': ('Opzioni di budget', 'Verifica i costi sconosciuti prima di prenotare. Considera meno notti, altre date o una destinazione più vicina; il risparmio non è garantito.'),
}


# Fixed headings keep all six locales compatible with the client's day-card parser.
LABELS = {
    'en': ('Overview', 'Flights', 'Where to stay', 'Day', 'Budget breakdown', 'Practical tips', 'Morning', 'Afternoon', 'Evening', 'Estimated cost', 'Unknown'),
    'ro': ('Prezentare generală', 'Zboruri', 'Cazare', 'Ziua', 'Buget estimativ', 'Sfaturi practice', 'Dimineața', 'După-amiaza', 'Seara', 'Cost estimat', 'Necunoscut'),
    'es': ('Resumen', 'Vuelos', 'Alojamiento', 'Día', 'Desglose del presupuesto', 'Consejos prácticos', 'Mañana', 'Tarde', 'Noche', 'Coste estimado', 'Desconocido'),
    'fr': ('Aperçu', 'Vols', 'Hébergement', 'Jour', 'Répartition du budget', 'Conseils pratiques', 'Matin', 'Après-midi', 'Soir', 'Coût estimé', 'Inconnu'),
    'de': ('Überblick', 'Flüge', 'Unterkunft', 'Tag', 'Budgetübersicht', 'Praktische Tipps', 'Morgen', 'Nachmittag', 'Abend', 'Geschätzte Kosten', 'Unbekannt'),
    'it': ('Panoramica', 'Voli', 'Alloggio', 'Giorno', 'Riepilogo del budget', 'Consigli pratici', 'Mattina', 'Pomeriggio', 'Sera', 'Costo stimato', 'Sconosciuto'),
}

WEEKDAYS = {
    'en': ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'),
    'ro': ('luni', 'marți', 'miercuri', 'joi', 'vineri', 'sâmbătă', 'duminică'),
    'es': ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'),
    'fr': ('lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche'),
    'de': ('Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'),
    'it': ('lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica'),
}

BUDGET_LABELS = {
    'en': ('Estimated total', 'Known estimated costs only; the full total is unknown.', 'Known estimated costs exceed your budget.'),
    'ro': ('Total estimat', 'Doar costurile estimate cunoscute; totalul complet este necunoscut.', 'Costurile estimate cunoscute depășesc bugetul.'),
    'es': ('Total estimado', 'Solo costes estimados conocidos; se desconoce el total completo.', 'Los costes estimados conocidos superan tu presupuesto.'),
    'fr': ('Total estimé', 'Uniquement les coûts estimés connus ; le total complet est inconnu.', 'Les coûts estimés connus dépassent votre budget.'),
    'de': ('Geschätzte Gesamtkosten', 'Nur bekannte geschätzte Kosten; die Gesamtkosten sind unbekannt.', 'Die bekannten geschätzten Kosten überschreiten dein Budget.'),
    'it': ('Totale stimato', 'Solo costi stimati noti; il totale completo è sconosciuto.', 'I costi stimati noti superano il budget.'),
}


def inline(value):
    # Model-provided text cannot introduce section/day headings into the adapter.
    return ' '.join(value.split())


def render_itinerary(plan, language, requested_budget=None):
    labels = LABELS[language]
    overview, flights, stay, day_label, budget, tips = labels[:6]
    def money(value):
        return labels[10] if value is None else f'{value:.2f} EUR'

    lines = [f'## {overview}', inline(plan.overview), f'## {flights}']
    lines.extend(f'- **{inline(option.route)}**: {inline(option.estimate)}' for option in plan.flights.options)
    lines.extend([inline(plan.flights.caveat), f'## {stay}', inline(plan.accommodation)])
    for day in plan.days:
        day_date = f' — {day.date.isoformat()} ({WEEKDAYS[language][day.date.weekday()]})' if day.date else ''
        lines.append(f'## {day_label} {day.number}{day_date}: {inline(day.title)}')
        for index, period in enumerate(('morning', 'afternoon', 'evening')):
            activities = [activity for activity in day.activities if activity.period == period]
            if not activities:
                continue
            lines.append(f'### {labels[6 + index]}')
            for activity in activities:
                place = f' ({inline(activity.place)})' if activity.place else ''
                lines.append(f'- **{inline(activity.title)}**{place}: {inline(activity.details)}')
                if activity.estimated_cost_eur is not None:
                    lines.append(f'  - {labels[9]}: {money(activity.estimated_cost_eur)}')
    lines.append(f'## {budget}')
    lines.extend(f'- **{inline(item.category)}**: {money(item.estimated_cost_eur)}. {inline(item.notes)}' for item in plan.budget)
    summary = budget_summary(plan, requested_budget if requested_budget is not None else Decimal('Infinity'))
    total_label, unknown_label, exceeded_label = BUDGET_LABELS[language]
    if summary['has_unknown_costs']:
        lines.append(f'**{labels[9]}: {summary["known_estimated_cost_eur"]} EUR**. {unknown_label}')
    else:
        lines.append(f'**{total_label}: {summary["estimated_total_eur"]} EUR**')
    if summary['exceeds_budget']:
        lines.append(exceeded_label)
    if summary['status'] != 'within_estimate':
        advice_title, fallback = ADVICE_LABELS[language]
        lines.append(f'### {advice_title}')
        lines.extend(f'- {inline(advice)}' for advice in (plan.budget_advice or [fallback]))
    lines.append(f'## {tips}')
    lines.extend(f'- {inline(tip)}' for tip in plan.practical_tips)
    return '\n\n'.join(lines)


def parse_crew_itinerary(result):
    structured = getattr(result, 'pydantic', None)
    if isinstance(structured, BaseModel):
        return Itinerary.model_validate(structured.model_dump())
    # CrewAI can return raw JSON if its Pydantic conversion did not succeed.
    raw = getattr(result, 'raw', result)
    return Itinerary.model_validate_json(raw)
