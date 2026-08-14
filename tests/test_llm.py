import sys
from types import SimpleNamespace

from orchestration import config
from orchestration.llm import AnthropicLLM, MockLLM


def test_anthropic_client_uses_bounded_retry_and_timeout(monkeypatch):
    captured = {}

    class FakeAnthropic:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=FakeAnthropic))
    monkeypatch.setattr(config, "LLM_MAX_RETRIES", 4)
    monkeypatch.setattr(config, "LLM_TIMEOUT_SECONDS", 90)

    AnthropicLLM(api_key="test-key", base_url="https://gateway.example")

    assert captured["max_retries"] == 4
    assert captured["timeout"] == 90
    assert captured["base_url"] == "https://gateway.example"
    assert captured["api_key"] == "test-key"


def test_mock_llm_records_token_budget():
    llm = MockLLM(handler=lambda _model, _system, _prompt: "ok")

    llm.complete(model="test", system="system", prompt="prompt", max_tokens=321)

    assert llm.calls[0]["max_tokens"] == 321


def test_optional_integer_settings_are_bounded_and_tolerate_typos(monkeypatch):
    monkeypatch.setenv("TEST_INTEGER_SETTING", "not-a-number")
    assert config.bounded_env_int("TEST_INTEGER_SETTING", 7, 1, 10) == 7
    monkeypatch.setenv("TEST_INTEGER_SETTING", "999")
    assert config.bounded_env_int("TEST_INTEGER_SETTING", 7, 1, 10) == 10
