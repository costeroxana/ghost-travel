# Ghost Travel itinerary crew

The Flask backend loads this CrewAI project from `crew.jsonc` and supplies the trip inputs. The three tasks research flights, find local attractions, and assemble the itinerary.

## Running

To run the crew directly, run the command below from this directory with your model provider credentials and `LATLNG_API_KEY` available in the environment. CrewAI prompts for the trip inputs.

```bash
crewai run
```

## Project Structure

- `agents/` - Agent definitions (JSONC)
- `crew.jsonc` - Crew definition with tasks and configuration
- `tools/find_places.py` - Museum lookup via LatLng
- `itinerary_models.py` - Pydantic task outputs and itinerary rendering
- `knowledge/` - Knowledge files for agents

> **Note:** `custom:<name>` tool references execute `tools/<name>.py` as local
> Python code when the crew loads. Only run crew projects from sources you
> trust.
