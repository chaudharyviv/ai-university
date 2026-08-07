import pytest

from agents.persona_agent import PersonaAgent
from models.persona_archetypes import CUSTOM_ARCHETYPE, PERSONA_ARCHETYPES, PERSONA_ARCHETYPE_OPTIONS
from models.schemas import PersonaEssentials, PersonaProfile
from prompts.persona_prompt import PERSONA_ESSENTIALS_SYSTEM_PROMPT, PERSONA_SYSTEM_PROMPT


def test_archetype_options_includes_custom_first():
    assert PERSONA_ARCHETYPE_OPTIONS[0] == CUSTOM_ARCHETYPE
    assert set(PERSONA_ARCHETYPE_OPTIONS[1:]) == set(PERSONA_ARCHETYPES)


def test_each_archetype_has_audience_level_and_tone():
    for name, archetype in PERSONA_ARCHETYPES.items():
        assert archetype["audience_level"], f"{name} missing audience_level"
        assert archetype["tone"], f"{name} missing tone"


# --- build_user_prompt branching ---------------------------------------------


def test_build_user_prompt_custom_matches_original_behavior(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    agent = PersonaAgent()
    prompt = agent.build_user_prompt(topic="Intro to Rust", persona_archetype=CUSTOM_ARCHETYPE)
    assert prompt == "Course topic: Intro to Rust"


def test_build_user_prompt_no_archetype_matches_original_behavior(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    agent = PersonaAgent()
    prompt = agent.build_user_prompt(topic="Intro to Rust")
    assert prompt == "Course topic: Intro to Rust"


def test_build_user_prompt_fixed_archetype_includes_fixed_fields(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    agent = PersonaAgent()
    prompt = agent.build_user_prompt(topic="Intro to Rust", persona_archetype="AI/Software Engineer")
    assert "Intro to Rust" in prompt
    assert PERSONA_ARCHETYPES["AI/Software Engineer"]["audience_level"] in prompt
    assert PERSONA_ARCHETYPES["AI/Software Engineer"]["tone"] in prompt
    assert "do not restate or redefine" in prompt


def test_build_user_prompt_rejects_unknown_archetype(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    agent = PersonaAgent()
    with pytest.raises(ValueError, match="Unknown persona_archetype"):
        agent.build_user_prompt(topic="Intro to Rust", persona_archetype="Astronaut")


# --- run() composition (mocked, no live API calls) ---------------------------


def _fake_response(content: str):
    from types import SimpleNamespace

    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20),
    )


def test_run_with_fixed_archetype_composes_full_profile(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    essentials_json = '{"prerequisites": ["basic algebra"], "learning_goals": ["explain gradient descent"]}'
    calls: list[dict] = []

    def fake_completion(model, messages, max_tokens):
        calls.append({"model": model, "system": messages[0]["content"]})
        return _fake_response(essentials_json)

    monkeypatch.setattr("agents.base.litellm.completion", fake_completion)
    monkeypatch.setattr("agents.base.litellm.completion_cost", lambda completion_response: 0.001)

    agent = PersonaAgent()
    result = agent.run(topic="Machine Learning", persona_archetype="AI/Software Engineer")

    assert result.success
    assert isinstance(result.output, PersonaProfile)
    assert result.output.audience_level == PERSONA_ARCHETYPES["AI/Software Engineer"]["audience_level"]
    assert result.output.tone == PERSONA_ARCHETYPES["AI/Software Engineer"]["tone"]
    assert result.output.prerequisites == ["basic algebra"]
    assert result.output.learning_goals == ["explain gradient descent"]
    assert result.metadata["persona_archetype"] == "AI/Software Engineer"
    # Confirms the essentials-only prompt was actually used, not the full one
    assert calls[0]["system"] == PERSONA_ESSENTIALS_SYSTEM_PROMPT


def test_run_with_custom_generates_full_profile_as_before(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    full_json = (
        '{"audience_level": "beginner", "tone": "friendly", '
        '"prerequisites": ["none"], "learning_goals": ["understand basics"]}'
    )
    calls: list[dict] = []

    def fake_completion(model, messages, max_tokens):
        calls.append({"system": messages[0]["content"]})
        return _fake_response(full_json)

    monkeypatch.setattr("agents.base.litellm.completion", fake_completion)
    monkeypatch.setattr("agents.base.litellm.completion_cost", lambda completion_response: 0.001)

    agent = PersonaAgent()
    result = agent.run(topic="Intro to Rust", persona_archetype=CUSTOM_ARCHETYPE)

    assert result.success
    assert result.output.audience_level == "beginner"
    assert "persona_archetype" not in result.metadata
    assert calls[0]["system"] == PERSONA_SYSTEM_PROMPT


def test_run_with_no_archetype_key_generates_full_profile(monkeypatch):
    # Simulates older callers / tests that don't pass persona_archetype at all.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    full_json = (
        '{"audience_level": "beginner", "tone": "friendly", '
        '"prerequisites": [], "learning_goals": ["x"]}'
    )
    monkeypatch.setattr("agents.base.litellm.completion", lambda **kw: _fake_response(full_json))
    monkeypatch.setattr("agents.base.litellm.completion_cost", lambda completion_response: 0.001)

    agent = PersonaAgent()
    result = agent.run(topic="Intro to Rust")

    assert result.success
    assert isinstance(result.output, PersonaProfile)
    assert result.output.audience_level == "beginner"


def test_run_reproducibility_audience_level_and_tone_are_never_llm_derived(monkeypatch):
    # The core promise of the hybrid approach: no matter what the model
    # returns for prerequisites/learning_goals, audience_level/tone must
    # always come from the fixed archetype, never from parsing the model's
    # response (there's no field for it in PersonaEssentials at all).
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    essentials_json = '{"prerequisites": [], "learning_goals": ["a"]}'
    monkeypatch.setattr("agents.base.litellm.completion", lambda **kw: _fake_response(essentials_json))
    monkeypatch.setattr("agents.base.litellm.completion_cost", lambda completion_response: 0.001)

    agent1 = PersonaAgent()
    result1 = agent1.run(topic="Topic A", persona_archetype="K-12 Student")
    agent2 = PersonaAgent()
    result2 = agent2.run(topic="Completely different topic B", persona_archetype="K-12 Student")

    assert result1.output.audience_level == result2.output.audience_level
    assert result1.output.tone == result2.output.tone
