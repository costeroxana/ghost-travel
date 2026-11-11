from pathlib import Path


def create_travel_crew():
    from crewai.project.crew_loader import load_crew

    definition = Path(__file__).with_name('agents') / 'crew.jsonc'
    crew, _ = load_crew(definition)
    return crew
