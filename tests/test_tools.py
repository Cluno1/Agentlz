from agentlz.tools.weather import get_weather


def test_weather_tool_basic():
    # The tool decorator returns a Tool object with "invoke" method
    out = get_weather.invoke("SF")
    assert "sunny" in out.lower()