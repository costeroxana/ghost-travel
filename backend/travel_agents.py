def create_travel_crew():
    from crewai import Agent, Crew, Process, Task
    from itinerary_models import FlightResearch, LocalResearch, Itinerary

    flight_hunter = Agent(
        role='Flight Logistics Expert',
        goal='Suggest plausible flight routes and clearly labeled planning estimates without claiming live verification.',
        backstory='''You advise travelers on airports, routing, and approximate travel budgets.
        You have no live flight-search or booking access. You distinguish general routing
        advice from verified schedules, fares, and availability, and never invent booking details.''',
        verbose=True,
        allow_delegation=False
    )

    local_explorer = Agent(
        role='Alternative Local Guide',
        goal='Discover authentic, non-touristy attractions and local culinary spots.',
        backstory='''You suggest local places from general knowledge. You have no live search
        access, so ratings, opening hours, availability and prices must be verified.
        You distinguish suggestions from verified recommendations.''',
        verbose=True,
        allow_delegation=False
    )

    chief_concierge = Agent(
        role='Chief Travel Coordinator',
        goal='Assemble flights and local spots into a perfectly timed, budget-friendly daily itinerary.',
        backstory='''You are a master of logistics and time management. You take flight data
        and attraction lists, check the traveler\'s budget, and structure a realistic
        day-by-day plan ensuring locations are geographically close to minimize travel time.''',
        verbose=True,
        allow_delegation=True
    )

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

    return Crew(
        agents=[flight_hunter, local_explorer, chief_concierge],
        tasks=[task_find_flights, task_find_local_spots, task_create_itinerary],
        process=Process.sequential,
        verbose=True
    )