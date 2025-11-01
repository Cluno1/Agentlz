from agentlz.config.settings import get_settings


def test_settings_defaults():
    s = get_settings()
    assert isinstance(s.model_name, str)
    assert s.system_prompt