"""
Tests for Phase 6's provider failover: if the primary model's completion
call itself raises (rate limit, timeout, outage), BaseAgent.run() should
automatically retry once against settings.fallback_model rather than
failing the whole agent - without ever making a real network call.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.persona_agent import PersonaAgent
from config import settings


def _fake_response(content: str):
    """Minimal stand-in for a litellm ModelResponse."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20),
    )


VALID_PERSONA_JSON = (
    '{"audience_level": "beginner", "tone": "friendly", '
    '"prerequisites": [], "learning_goals": ["understand basics"]}'
)


def test_run_falls_back_to_second_model_when_primary_raises(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    calls: list[str] = []

    def fake_completion(model, messages, max_tokens):
        calls.append(model)
        if model == settings.primary_model:
            raise RuntimeError("simulated provider outage")
        return _fake_response(VALID_PERSONA_JSON)

    monkeypatch.setattr("agents.base.litellm.completion", fake_completion)
    monkeypatch.setattr("agents.base.litellm.completion_cost", lambda completion_response: 0.001)

    agent = PersonaAgent()
    result = agent.run(topic="Intro to Rust")

    assert result.success is True
    assert calls == [settings.primary_model, settings.fallback_model]
    assert result.model_used == settings.fallback_model
    assert result.metadata.get("failed_over") is True


def test_run_succeeds_on_primary_without_touching_fallback(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    calls: list[str] = []

    def fake_completion(model, messages, max_tokens):
        calls.append(model)
        return _fake_response(VALID_PERSONA_JSON)

    monkeypatch.setattr("agents.base.litellm.completion", fake_completion)
    monkeypatch.setattr("agents.base.litellm.completion_cost", lambda completion_response: 0.001)

    agent = PersonaAgent()
    result = agent.run(topic="Intro to Rust")

    assert result.success is True
    assert calls == [settings.primary_model]
    assert result.model_used == settings.primary_model
    assert result.metadata.get("failed_over") is False


def test_run_fails_cleanly_when_both_models_raise(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_completion(model, messages, max_tokens):
        raise RuntimeError(f"simulated outage on {model}")

    monkeypatch.setattr("agents.base.litellm.completion", fake_completion)

    agent = PersonaAgent()
    result = agent.run(topic="Intro to Rust")

    assert result.success is False
    assert "simulated outage" in result.error
    assert result.model_used == settings.fallback_model  # the last attempted model


def test_schema_validation_failure_does_not_trigger_failover(monkeypatch):
    # A model that responds with garbage JSON is a formatting problem, not
    # a provider problem - should NOT retry against the fallback model.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    calls: list[str] = []

    def fake_completion(model, messages, max_tokens):
        calls.append(model)
        return _fake_response("this is not json at all")

    monkeypatch.setattr("agents.base.litellm.completion", fake_completion)
    monkeypatch.setattr("agents.base.litellm.completion_cost", lambda completion_response: 0.001)

    agent = PersonaAgent()
    result = agent.run(topic="Intro to Rust")

    assert result.success is False
    assert "validation" in result.error
    assert calls == [settings.primary_model]  # only one attempt, no failover


def test_prompt_building_failure_never_calls_the_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def fake_completion(*args, **kwargs):
        pytest.fail("litellm.completion should never be called when prompt-building fails")

    monkeypatch.setattr("agents.base.litellm.completion", fake_completion)

    agent = PersonaAgent()
    result = agent.run()  # missing required 'topic'

    assert result.success is False
    assert "topic" in result.error
