# Ghost Travel

An Expo / React Native travel planner with a Flask and CrewAI backend.

## Features

- Departure and destination city autocomplete, quick suggestions, and route swapping.
- Departure calendar, editable total EUR budget, and trip length from 1 to 30 days.
- Animated travel scene during generation, with automatic scrolling and mobile keyboard handling.
- Readable Markdown itineraries with individually collapsible day cards.
- Destination photo gallery inside completed itineraries, with Wikimedia attribution and retry controls.
- English, Romanian, Spanish, French, German, and Italian UI and itinerary generation; the selected language is saved locally.
- Persistent SQLite itinerary cache keyed by route, budget, days, departure date, and language. Entries expire after 24 hours.
- A shared limit of five new itinerary generations per minute per backend process. Cached responses do not consume the limit.

## Project structure

- `src/app/`: Expo Router screens and root layout.
- `src/components/`: trip form, calendar, animation, gallery, and itinerary cards.
- `src/i18n/`: six-language translation catalog and saved language preference.
- `backend/`: Flask API, agents, photo lookup, persistent cache, and tests.

## Frontend

Requires a Node version compatible with Expo SDK 57 (Node 22.13 or newer).

```powershell
npm ci
npx expo start --go
```

The committed `.env` files contain configuration placeholders only. Add credentials locally and do not commit them.

`EXPO_PUBLIC_API_URL` is the Python backend base URL, without `/api/itinerary`.
For web on the same computer, use `http://localhost:5000`. For a physical phone,
use the computer's Wi-Fi IPv4 address, for example `http://192.168.100.42:5000`.
This frontend variable is public: keep OpenAI credentials in the backend only.

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
.\.venv\Scripts\python.exe app.py
```

For physical-device testing, set `HOST=0.0.0.0` in the backend environment and
allow Python through the Windows firewall on the private network. Debug mode
is disabled. The API runs on port 5000.

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

- `origin` and `destination`: different cities, each 2–100 characters.
- `budget`: total EUR budget from 1 to 100,000, with at most two decimal places.
- `days`: a whole number from 1 to 30. The departure date is Day 1.
- `departure_date`: `YYYY-MM-DD`, today or later. Backend validation uses the
  Europe/Bucharest time zone. Legacy clients may omit this field.
- `language`: `en`, `ro`, `es`, `fr`, `de`, or `it`; defaults to `en`.

The response includes the route, budget, currency, day count, departure and
last-trip dates, selected language, Markdown under `text_itinerary`, and a
`cached` boolean. Invalid input returns 400; too many new generations return
429 with a `Retry-After` header; generation failure returns a JSON error with 502.
`GET /api/itinerary` remains available for the original demo and query parameters.

`GET /api/destination-photos?destination=Rome%2C%20Italy` returns up to six
destination images with photographer, license, and source URL metadata.
Photos appear inside a completed itinerary and load independently of the
agents. Image lookup results refresh after 24 hours. Source photos may have
been taken earlier; they are not live destination images.

## Cache behavior

Identical requests reuse a saved itinerary for 24 hours, including across
backend restarts. City casing and repeated whitespace are normalized, and
equivalent budgets such as `300` and `300.00` share a cache entry. Departure
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
.\.venv\Scripts\python.exe -m unittest -q test_app_security test_destination_photos
```

Backend tests mock the agents and photo provider, so they do not make paid
OpenAI calls. The current code has 24 passing backend tests. Full-project
lint reports a pre-existing `react-hooks/set-state-in-effect` issue in
`src/hooks/use-color-scheme.web.ts`; the changed app files pass lint.