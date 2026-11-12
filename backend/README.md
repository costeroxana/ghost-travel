# Ghost Travel backend

The Expo app sends trip requests to Flask. Flask validates the request, checks the itinerary cache, and runs the CrewAI itinerary crew on a cache miss. It validates the returned itinerary, calculates the budget summary, and renders the result for the app.

## Run locally

From this directory, activate a Python 3.12 virtual environment and run `python -m pip install -r requirements.txt`. Create a local `.env` with your model provider credentials (such as `OPENAI_API_KEY` for the default OpenAI provider). Set `LATLNG_API_KEY` to enable museum lookups.

```powershell
.\start.cmd
```

Flask listens on `127.0.0.1:5000` by default. For a physical device on your local network, set `HOST=0.0.0.0` in the backend environment and point the Expo app's `EXPO_PUBLIC_API_URL` at the backend's LAN address.

## Wikivoyage guide sources

The itinerary endpoint looks up a guide for the requested destination and keeps searchable passages in a local SQLite index. It tries the requested language and can fall back to English. Itineraries can still be generated when a guide is unavailable. Supported citations appear under **Guide sources** in the app.

From this directory, you can also index and search a guide before generating an itinerary.

```powershell
python guide_index.py build Bucharest
python guide_index.py search Bucharest "Village Museum and a nearby park"
```

Guide text comes from [Wikivoyage contributors](https://www.wikivoyage.org/) under [CC BY-SA 4.0](https://en.wikivoyage.org/wiki/Wikivoyage:Copyleft). The backend stores the index as runtime data and links to the article revision used for each citation.

## Where to make changes

| Path | Responsibility |
| --- | --- |
| [app.py](app.py) | HTTP routes, input validation, rate limits, and response handling |
| [crew_loader.py](crew_loader.py) | Loads the active CrewAI project from disk |
| [crew/crew.jsonc](crew/crew.jsonc) | Flight research, local research, and itinerary tasks, with their dependencies and output schemas |
| [crew/agents/](crew/agents/) | Agent roles, goals, and settings |
| [crew/tools/find_places.py](crew/tools/find_places.py) | Validates model tool arguments and queries LatLng for museums near the destination |
| [crew/itinerary_models.py](crew/itinerary_models.py) | Pydantic schemas, itinerary validation, budget calculations, and rendering |
| [destination_photos.py](destination_photos.py) | Attributed destination images for the app gallery |
| [itinerary_cache.py](itinerary_cache.py) and [agent_metrics.py](agent_metrics.py) | SQLite caching and generation metrics |

`POST /api/itinerary` is the app's trip-generation entry point. `GET /api/destination-photos?destination=Rome%2C%20Italy` serves the gallery. On a fresh itinerary request, Local Explorer is instructed to call the museum tool. A cache hit reuses the saved itinerary. The coordinator is instructed to schedule a museum returned by LatLng. The backend adds OpenStreetMap via LatLng credit to matching activities before caching the itinerary.

The backend stores its current cache and metrics in `itinerary_cache.sqlite3` and `agent_metrics.sqlite3`. Run `python agent_metrics.py` to inspect recorded runs locally.

## Tests and experiments

- [tests/](tests/) contains the backend tests. Run `python -m unittest discover` from the backend root. The route tests mock crew generation and make no paid model calls.
- [experiments/](experiments/) contains the optional agent comparison, archived café prototype, and web demo recordings. See [what each experiment is for](experiments/README.md).
