from langchain.tools import tool


@tool
def get_weather(city: str) -> str:
    """Get weather for a given city (demo tool)."""
    return f"It's always sunny in {city}!"