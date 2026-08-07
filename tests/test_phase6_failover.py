"""
Tests for Phase 6's provider failover: if the primary model's completion
call itself raises (rate limit, timeout, outage), BaseAgent.run() should
automatically retry once against settings.fallback_model rather than
failing the whole agent - without ever making a real network call.

These tests monkeypatch settings attributes directly (not just env vars)
because `config.settings` is a singleton constructed at import time;
monkeypatch.setenv alone does not refresh pydantic-settings fields and
would make CI (Anthropic-only) diverge from local .env-with-both-keys.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agents.persona_agent import PersonaAgent
from agents.research_agent import ResearchAgent
from config import settings


PRIMARY = "openai/gpt-4o-mini"
FALLBACK = "anthropic/claude-sonnet-4-5"


@pytest.fixture
def both_providers(monkeypatch):
    """Deterministic two-provider routing, independent of CI/.env keys."""
    monkeypatch.setattr(settings, "primary_model", PRIMARY)
    monkeypatch.setattr(settings, "fallback_model", FALLBACK)
    monkeypatch.setattr(type(settings), "has_openai", property(lambda self: True))
    monkeypatch.setattr(type(settings), "has_anthropic", property(lambda self: True))


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

VALID_RESEARCH_JSON = (
    '{"topic": "Rust", '
    '"findings": [{"title": "Book", "url": "https://example.com", "key_points": ["ownership"]}], '
    '"summary": "practical intro"}'
)


def test_run_falls_back_to_second_model_when_primary_raises(both_providers, monkeypatch):
    calls: list[str] = []

    def fake_completion(model, messages, max_tokens):
        calls.append(model)
        if model == PRIMARY:
            raise RuntimeError("simulated provider outage")
        return _fake_response(VALID_PERSONA_JSON)

    monkeypatch.setattr("agents.base.litellm.completion", fake_completion)
    monkeypatch.setattr("agents.base.litellm.completion_cost", lambda completion_response: 0.001)

    agent = PersonaAgent()
    result = agent.run(topic="Intro to Rust")

    assert result.success is True
    assert calls == [PRIMARY, FALLBACK]
    assert result.model_used == FALLBACK
    assert result.metadata.get("failed_over") is True


def test_run_succeeds_on_primary_without_touching_fallback(both_providers, monkeypatch):
    calls: list[str] = []

    def fake_completion(model, messages, max_tokens):
        calls.append(model)
        return _fake_response(VALID_PERSONA_JSON)

    monkeypatch.setattr("agents.base.litellm.completion", fake_completion)
    monkeypatch.setattr("agents.base.litellm.completion_cost", lambda completion_response: 0.001)

    agent = PersonaAgent()
    result = agent.run(topic="Intro to Rust")

    assert result.success is True
    assert calls == [PRIMARY]
    assert result.model_used == PRIMARY
    assert result.metadata.get("failed_over") is False


def test_run_fails_cleanly_when_both_models_raise(both_providers, monkeypatch):
    def fake_completion(model, messages, max_tokens):
        raise RuntimeError(f"simulated outage on {model}")

    monkeypatch.setattr("agents.base.litellm.completion", fake_completion)

    agent = PersonaAgent()
    result = agent.run(topic="Intro to Rust")

    assert result.success is False
    assert "simulated outage" in result.error
    assert result.model_used == FALLBACK  # the last attempted model


def test_schema_validation_failure_does_not_trigger_failover(both_providers, monkeypatch):
    # A model that responds with garbage JSON is a formatting problem, not
    # a provider problem - should NOT retry against the fallback model.
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
    assert calls == [PRIMARY]  # only one attempt, no failover


def test_prompt_building_failure_never_calls_the_model(both_providers, monkeypatch):
    def fake_completion(*args, **kwargs):
        pytest.fail("litellm.completion should never be called when prompt-building fails")

    monkeypatch.setattr("agents.base.litellm.completion", fake_completion)

    agent = PersonaAgent()
    result = agent.run()  # missing required 'topic'

    assert result.success is False
    assert "topic" in result.error


def test_failover_skipped_when_fallback_provider_has_no_credentials(monkeypatch):
    """Don't burn a second call when the fallback key isn't configured."""
    monkeypatch.setattr(settings, "primary_model", PRIMARY)
    monkeypatch.setattr(settings, "fallback_model", FALLBACK)
    monkeypatch.setattr(type(settings), "has_openai", property(lambda self: True))
    monkeypatch.setattr(type(settings), "has_anthropic", property(lambda self: False))

    calls: list[str] = []

    def fake_completion(model, messages, max_tokens):
        calls.append(model)
        raise RuntimeError("simulated primary outage")

    monkeypatch.setattr("agents.base.litellm.completion", fake_completion)

    agent = PersonaAgent()
    result = agent.run(topic="Intro to Rust")

    assert result.success is False
    assert calls == [PRIMARY]
    assert result.model_used == PRIMARY


def test_research_agent_falls_back_when_primary_raises(both_providers, monkeypatch):
    models_used: list[str] = []

    class FakeLiteLLMModel:
        def __init__(self, model_id, max_tokens=None):
            models_used.append(model_id)
            self.model_id = model_id

    class FakeToolCallingAgent:
        def __init__(self, tools, model, max_steps, instructions):
            self.model = model
            self.monitor = MagicMock()
            self.monitor.get_total_token_counts.return_value = SimpleNamespace(
                input_tokens=5, output_tokens=10
            )

        def run(self, prompt):
            if self.model.model_id == PRIMARY:
                raise RuntimeError("simulated research provider outage")
            return VALID_RESEARCH_JSON

    monkeypatch.setattr("agents.research_agent.LiteLLMModel", FakeLiteLLMModel)
    monkeypatch.setattr("agents.research_agent.ToolCallingAgent", FakeToolCallingAgent)

    agent = ResearchAgent()
    result = agent.run(topic="Rust")

    assert result.success is True
    assert models_used == [PRIMARY, FALLBACK]
    assert result.model_used == FALLBACK
    assert result.metadata.get("failed_over") is True


# --- Cost-estimation-failure visibility (red-team fix) -----------------------


def test_cost_estimation_failure_is_surfaced_not_silently_swallowed(monkeypatch, both_providers):
    # If litellm.completion_cost() itself raises (e.g. unpriced model),
    # the call must still succeed with cost=0.0, but this must be visible
    # in metadata rather than silently indistinguishable from "this call
    # genuinely cost nothing" - the latter would let the cost ceiling be
    # bypassed with no way to notice.
    monkeypatch.setattr("agents.base.litellm.completion", lambda **kw: _fake_response(VALID_PERSONA_JSON))

    def broken_cost(completion_response):
        raise RuntimeError("model not in pricing table")

    monkeypatch.setattr("agents.base.litellm.completion_cost", broken_cost)

    agent = PersonaAgent()
    result = agent.run(topic="Intro to Rust")

    assert result.success is True
    assert result.estimated_cost_usd == 0.0
    assert result.metadata.get("cost_estimation_failed") is True


def test_cost_estimation_success_sets_flag_false(monkeypatch, both_providers):
    monkeypatch.setattr("agents.base.litellm.completion", lambda **kw: _fake_response(VALID_PERSONA_JSON))
    monkeypatch.setattr("agents.base.litellm.completion_cost", lambda completion_response: 0.002)

    agent = PersonaAgent()
    result = agent.run(topic="Intro to Rust")

    assert result.estimated_cost_usd == 0.002
    assert result.metadata.get("cost_estimation_failed") is False


# --- smolagents monitor API guard (red-team fix) -----------------------------


def test_research_agent_degrades_gracefully_when_monitor_api_missing(monkeypatch, both_providers):
    # Simulates a smolagents version where .monitor.get_total_token_counts()
    # no longer exists / raises AttributeError - the whole agent must not
    # crash over a cost-tracking nicety, it should degrade to 0 tokens.
    VALID_RESEARCH_JSON = (
        '{"topic": "Rust", "findings": [], "summary": "Rust is a systems language."}'
    )

    class BrokenMonitor:
        def get_total_token_counts(self):
            raise AttributeError("monitor API changed in this smolagents version")

    class FakeLiteLLMModel:
        def __init__(self, model_id, max_tokens=None):
            self.model_id = model_id

    class FakeToolCallingAgent:
        def __init__(self, tools, model, max_steps, instructions):
            self.model = model
            self.monitor = BrokenMonitor()

        def run(self, prompt):
            return VALID_RESEARCH_JSON

    monkeypatch.setattr("agents.research_agent.LiteLLMModel", FakeLiteLLMModel)
    monkeypatch.setattr("agents.research_agent.ToolCallingAgent", FakeToolCallingAgent)

    agent = ResearchAgent()
    result = agent.run(topic="Rust")

    assert result.success is True
    assert result.input_tokens == 0
    assert result.output_tokens == 0
