from config import Settings


def test_settings_load_with_defaults(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    s = Settings()
    assert s.has_anthropic is True
    assert s.primary_model == "openai/gpt-4o-mini"
    assert s.fallback_model.startswith("anthropic/")
    assert s.max_tokens == 1000


def test_validate_at_least_one_provider_raises_when_none_set(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    s = Settings(anthropic_api_key="", openai_api_key="")
    try:
        s.validate_at_least_one_provider()
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
