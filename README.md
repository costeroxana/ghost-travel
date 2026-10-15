# Ghost Travel

<p align="center"><img src="assets/brand/ghost-travel-github-icon.png" alt="Ghost Travel logo" width="160" /></p>

A travel planner for Android, iOS, and web, built with Expo and React Native, powered by a Flask and CrewAI backend. Tested on web and Android; iOS is configured but has not been verified on a device.

## Demo

### Web

https://github.com/user-attachments/assets/a5c03f01-0487-4340-be18-c70d5ccf22e8

## Features

- Departure and destination city autocomplete from a predefined local list, quick suggestions, and route swapping. Manual city entry is allowed; no external city-search API is used.
- Departure calendar, editable total EUR budget, and trip length from 1 to 30 days.
- Animated travel scene during generation, with automatic scrolling and mobile keyboard handling.
- Readable Markdown itineraries with individually collapsible day cards.
- Destination photo gallery inside completed itineraries, with Wikimedia attribution and retry controls.
- English, Romanian, Spanish, French, German, and Italian UI and itinerary generation; the selected language is saved locally.
- Persistent SQLite itinerary cache keyed by route, budget, days, departure date, and language. Entries expire after 24 hours.
- A shared limit of five new itinerary generations per minute per backend process. Cached responses do not consume the limit.

## How the AI agents work

Ghost Travel uses a CrewAI crew with three specialized roles. They are separate agent configurations with different instructions and structured output models, not separately trained models. The workflow is supplied with the requested route, departure date, trip length, total EUR budget, and output language; each task uses the fields relevant to its role.

| Agent | Responsibility | Structured output |
| --- | --- | --- |
| Flight Logistics Expert | Suggests potential airports and routes, broad travel-time and fare estimates, and what needs verification before booking. | `FlightResearch`: route options, estimates, and a verification caveat. |
| Alternative Local Guide | Suggests attractions and restaurants, with neighborhood information, descriptions, estimated costs, and uncertainty notes. | `LocalResearch`: places and caveats. |
| Chief Travel Coordinator | Combines the specialists’ suggestions into daily activities, accommodation advice, budget categories, practical tips, and budget adjustment options. | `Itinerary`: the complete structured travel plan. |

### Execution and collaboration

The tasks run **sequentially**, rather than in parallel: flight research first, local suggestions second, and itinerary coordination last. The coordinator explicitly receives both specialists’ task outputs as context. It is also allowed to delegate clarification requests to the other agents; the two specialists cannot delegate further.

The coordinator is instructed to group activities by area and keep arrival and departure days flexible because actual flight schedules are unknown. These instructions are not geographic or schedule validation. If costs appear too high, it should explain the limitation and propose adjustments instead of inventing lower prices. Unknown costs remain unknown.

### From a request to the displayed itinerary

1. **Validate the request.** Flask checks city text, budget, trip length, departure date, and language. City names are not checked against a geographic database.
2. **Check the cache.** An identical request completed within the last 24 hours returns immediately without running the agents. On a cache miss, the generation rate limit applies.
3. **Run a fresh crew copy.** The three tasks produce typed Pydantic results. The coordinator uses the specialists’ outputs to assemble the final plan.
4. **Check and prepare the plan in Python.** The backend checks day count and numbering, derives dates and weekdays from the requested departure date, checks budget categories, and calculates totals. Missing core costs prevent a complete affordability assessment. These are consistency checks, not verification of real-world travel information.
5. **Render and save.** Valid structured data is cached and converted into localized Markdown for the existing itinerary cards. Invalid results are not cached. Destination photos load separately after the itinerary is ready.

Local measurements record each task’s duration, token usage when available, and success or failure. These measurements help assess the value of each agent; the three-agent workflow remains the app’s default. See the [workflow comparison](backend/AGENT_EVALUATION.md) for an initial benchmark and its limitations.

### What the agents can verify

The agents currently work from model knowledge and **have no live flight-search, restaurant-search, or booking tools**. Their recommendations, opening hours, route availability, and prices require independent verification. Destination photos come from a separate Wikimedia lookup; they are not evidence that the agents performed live research. Python validation improves consistency but cannot establish factual accuracy.

## Project structure

- `src/app/`: Expo Router screens and root layout.
- `src/components/`: trip form, calendar, animation, gallery, and itinerary cards.
- `src/i18n/`: six-language translation catalog and saved language preference.
- `backend/`: Flask API, agents, photo lookup, persistent cache, and tests.

## Frontend

Use a supported Node.js release for Expo SDK 57, for example Node 22.x starting at 22.13.0 or Node 24.x starting at 24.3.0. See the [Expo SDK compatibility table](https://docs.expo.dev/versions/v57.0.0/).

```powershell
npm ci
npx expo start --go
```

The committed `.env` files contain configuration placeholders only. Add credentials locally and do not commit them.

`EXPO_PUBLIC_API_URL` is the Python backend base URL, without `/api/itinerary`.
For web on the same computer, use `http://localhost:5000`. For a physical phone,
use the computer's Wi-Fi IPv4 address in the frontend `.env`, for example `http://192.168.100.42:5000`.
This frontend variable is public: keep OpenAI credentials in the backend only.

Restart Expo after changing `EXPO_PUBLIC_API_URL`. This value overrides the platform fallback URLs; a phone needs a reachable computer address, not `localhost`.

Press `w` for web, or scan the Expo Go QR code on your phone. The phone and
computer need to share a Wi-Fi network. If Metro is inaccessible over LAN,
`npx expo start --go --tunnel` can tunnel Metro; the Python API still needs
its own reachable network address. If the CLI asks whether to log in, choose
an option and press Enter before scanning the QR again.

To verify the phone can reach Metro, open `http://YOUR_PC_IP:8081/status`
in its browser; the response should be `packager-status:running`. To verify
the Python connection without generating an itinerary, open
`http://YOUR_PC_IP:5000/api/destination-photos?destination=Rome%2C%20Italy`.

## Environment configuration

Two sanitized configuration files are tracked in Git:

- `.env`: `EXPO_PUBLIC_API_URL`, the frontend's backend base URL.
- `backend/.env`: `HOST` and an empty `OPENAI_API_KEY` placeholder.

Enter your own OpenAI key in your local `backend/.env`. No OpenAI key is
included in the repository. Before staging or pushing environment changes,
ensure the committed `OPENAI_API_KEY` value stays empty. A `.gitignore` rule
does not protect secrets in a file that Git already tracks.

For this development checkout, environment files can be kept out of routine
staging with:

```powershell
git update-index --skip-worktree .env backend/.env
```

This is a local Git setting, not a security guarantee or a setting inherited
by fresh clones. No `.env.example` files are required.

## Backend

The complete backend source is in `backend/`. Python 3.12 is the tested version.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Set `OPENAI_API_KEY` in `backend/.env`, then start the local development server:

```powershell
.\.venv\Scripts\python.exe -X utf8 app.py
```

For physical-device testing, set `HOST=0.0.0.0` in the backend environment and
allow Python through the Windows firewall on the private network. Debug mode
is disabled. The API runs on port 5000 and defaults to `127.0.0.1` when `HOST` is not set. It currently has no authentication and is intended for local development, not an exposed public service.

The SQLite cache is created automatically next to `app.py` and is excluded
from Git. Images are looked up separately from itinerary generation and never
trigger OpenAI calls. Flight details and costs are generated estimates.

## API

`POST /api/itinerary` accepts a JSON request:

```json
{
  "origin": "Bucharest, Romania",
  "destination": "Rome, Italy",
  "budget": "300.00",
  "days": 3,
  "departure_date": "2027-06-15",
  "language": "en"
}
```

- `origin` and `destination`: city text of 2–100 characters, different after case and whitespace normalization. This does not establish that the names refer to different real-world cities.
- `budget`: total EUR budget from 1 to 100,000, with at most two decimal places; defaults to 300 when omitted.
- `days`: a whole number from 1 to 30; defaults to 3 when omitted. The departure date is Day 1.
- `departure_date`: `YYYY-MM-DD`, today or later. Backend validation uses the
  Europe/Bucharest time zone. Legacy clients may omit this field.
- `language`: `en`, `ro`, `es`, `fr`, `de`, or `it`; defaults to `en`.

The response includes the route, budget, currency, day count, departure and
last-trip dates, selected language, the structured `itinerary`, computed `budget_summary`,
Markdown under `text_itinerary`, and a `cached` boolean. Invalid input returns 400; too many new generations return
429 with a `Retry-After` header; generation failure returns a JSON error with 502.
`GET /api/itinerary` remains available for the original demo and query parameters.

`GET /api/destination-photos?destination=Rome%2C%20Italy` returns up to six
destination images with photographer, license, and source URL metadata.
Photos appear inside a completed itinerary and load independently of the
agents. Photo metadata uses a process-local in-memory cache with a 24-hour lifetime; expired entries are refreshed on the next request, not on a background schedule. Source photos may have
been taken earlier; they are not live destination images. Invalid destination text returns 400; a provider exception returns 503; no matching images returns an empty `photos` list. The retired singular `/api/destination-photo` route is not available.

### Structured agent output

All three CrewAI tasks use Pydantic output models: flight research, local places, and the final itinerary. The API returns an `itinerary` object with days, activities, ISO dates, and estimated EUR costs, alongside the existing `text_itinerary` Markdown used by the app. Unknown costs are `null`; zero represents an estimated free item, not a verified free offer. Costs are serialized as decimal strings to preserve precision.

The backend renders localized headings for all six languages and caches the structured JSON for 24 hours. Invalid structured output returns the existing generation error and is not cached. Python validates the requested day count and unique consecutive day numbers, orders days, and derives dates and localized weekdays from the requested departure date. Without a departure date, day dates remain null. Duplicate budget category labels are rejected. Costs are rounded to cents before summing; the API returns a computed `budget_summary`, and the displayed total stays unknown if any category cost is unknown. Known costs exceeding the requested budget are flagged. Plans with missing, repeated, or extra days are rejected before caching; plans with unknown budget costs remain valid and are marked accordingly. These checks do not verify real-world prices, schedules, or whether every expense has been included. No external research tools have been added.

### Budget feasibility and agent metrics

Budget rows use distinct typed categories. Missing flights, accommodation, food, activities or local transport costs remain unknown, never zero. `budget_summary.status` is `over_budget`, `unknown`, or `within_estimate`; this is an estimate, not a guarantee of affordability. Over-budget and uncertain plans show localized adjustment suggestions without inventing cheaper fares.

New generations record task duration and token-counter deltas when available, task completion/failure/not-started status, total run duration, and run-level error types in local `backend/agent_metrics.sqlite3` (last 1,000 runs). Prompts, itinerary text, credentials and route inputs are not stored there. Shared model counters are deduplicated, task usage includes any delegation, and cached requests create no agent run. Token counts are measured usage, not a currency cost estimate. Missing provider counters remain unavailable.

From `backend/`, inspect the latest measurements with `.\.venv\Scripts\python.exe -X utf8 agent_metrics.py` (latest 10 runs). To explicitly run a model-call comparison of the normal crew with a single coordinator, use `.\.venv\Scripts\python.exe -X utf8 compare_agents.py --live`. This uses the configured API account and writes `agent_comparison.json`; one example measures latency and usage, not recommendation quality. The app continues to use all three agents.

## Cache behavior

Identical requests reuse a saved itinerary for 24 hours, including across
backend restarts. City casing and repeated whitespace are normalized, and
equivalent budgets such as `300` and `300.00` share a cache entry. A format version in `backend/itinerary_cache.py` invalidates older generations when bumped; changing model or prompt settings requires updating that version to prevent reuse of responses from older settings. Departure
date and language are part of the key. Failed generations are never saved.
An expired entry is regenerated on the next matching request.

Concurrent matching requests in the same backend process share one generation.
The generation lock and rate limit are process-local; multi-worker deployment
needs shared coordination. This repository currently targets local development.

## Checks

From the project root:

```powershell
npx tsc --noEmit
npx expo lint
```

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m unittest -q test_app_security test_destination_photos test_itinerary_models test_agent_metrics
```

Backend tests mock the agents and photo provider, so they do not make paid
OpenAI calls. Verified on 2026-10-15: 44 backend tests, TypeScript, and full-project lint pass. The web color-scheme hook uses a server-compatible subscription: static rendering and initial hydration use the light theme, followed by the system preference on the client.