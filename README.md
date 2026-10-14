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
its own reachable network address.

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