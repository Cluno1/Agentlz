from typing import Any

from langchain.agents import create_agent

from ..config.settings import get_settings
from ..core.model_factory import get_model
from ..tools.weather import get_weather


def build_agent():
    settings = get_settings()
    model = get_model(settings)
    agent = create_agent(
        model=model,
        tools=[get_weather],
        system_prompt=settings.system_prompt,
    )
    return agent


def ask(message: str) -> str:
    """Send a message to the agent and return the response text."""
    agent = build_agent()
    result: Any = agent.invoke({"messages": [{"role": "user", "content": message}]})

    if isinstance(result, dict):
        # Handle common structured outputs from agents
        return (
            result.get("output")
            or result.get("final_output")
            or result.get("structured_response")
            or str(result)
        )
    return str(result)