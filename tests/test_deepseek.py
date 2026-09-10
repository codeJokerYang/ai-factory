import sys
from types import SimpleNamespace

import pytest

from orchestration import config
from orchestration.agents.planner import Planner
from orchestration.llm import AnthropicLLM, MockLLM


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch):
    for name in ['FACTORY_PROVIDER', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN',
                 'DEEPSEEK_API_KEY', 'DEEPSEEK_MODEL', 'FACTORY_MODEL', 'FACTORY_PLANNER_MODEL']:
        monkeypatch.delenv(name, raising=False)


def test_local_deepseek_key_selects_official_endpoint(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-only')
    monkeypatch.setenv('ANTHROPIC_BASE_URL', 'https://unrelated.example')
    assert config.get_provider() == 'deepseek'
    assert config.get_api_key() == 'test-only'
    assert config.get_base_url() == 'https://api.deepseek.com/anthropic'
    assert Planner(MockLLM()).model == 'deepseek-chat'


def test_explicit_provider_ignores_other_provider_credentials(monkeypatch):
    captured = {}
    class FakeAnthropic:
        def __init__(self, **kwargs): captured.update(kwargs)
    monkeypatch.setitem(sys.modules, 'anthropic', SimpleNamespace(Anthropic=FakeAnthropic))
    monkeypatch.setenv('FACTORY_PROVIDER', 'deepseek')
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'deepseek-test')
    monkeypatch.setenv('ANTHROPIC_AUTH_TOKEN', 'other-test')
    AnthropicLLM()
    assert captured['api_key'] == 'deepseek-test'
    assert 'auth_token' not in captured
    assert captured['base_url'] == 'https://api.deepseek.com/anthropic'


def test_anthropic_existing_configuration_keeps_priority(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'deepseek-test')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'anthropic-test')
    assert config.get_provider() == 'anthropic'
    assert config.get_api_key() == 'anthropic-test'


def test_model_can_be_overridden_after_import(monkeypatch):
    monkeypatch.setenv('FACTORY_PROVIDER', 'deepseek')
    monkeypatch.setenv('FACTORY_PLANNER_MODEL', 'chosen-model')
    assert Planner(MockLLM()).model == 'chosen-model'


def test_explicit_deepseek_requires_its_own_key():
    import os
    from unittest.mock import patch
    with patch.dict(os.environ, {'FACTORY_PROVIDER': 'deepseek'}):
        with pytest.raises(ValueError, match='DEEPSEEK_API_KEY'):
            AnthropicLLM()
