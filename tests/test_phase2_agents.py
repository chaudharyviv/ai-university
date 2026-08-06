import pytest

import agents  # noqa: F401 - triggers agent registration
from agents.base import list_registered_agents
from agents.curriculum_agent import CurriculumAgent
from agents.notebook_agent import NotebookAgent
from agents.persona_agent import PersonaAgent
from agents.research_agent import ResearchAgent
from models.schemas import CourseOutline, Lesson, PersonaProfile, ResearchBrief


def test_all_phase2_agents_registered():
    assert {"persona", "research", "curriculum", "notebook"} <= set(list_registered_agents())


def test_persona_agent_requires_topic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    agent = PersonaAgent()
    with pytest.raises(ValueError, match="topic"):
        agent.build_user_prompt()


def test_persona_agent_builds_prompt_from_topic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    agent = PersonaAgent()
    prompt = agent.build_user_prompt(topic="Intro to Rust")
    assert "Intro to Rust" in prompt


def test_research_agent_requires_topic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    agent = ResearchAgent()
    with pytest.raises(ValueError, match="topic"):
        agent.build_user_prompt()


def test_curriculum_agent_requires_persona_and_research(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    agent = CurriculumAgent()
    with pytest.raises(ValueError, match="persona"):
        agent.build_user_prompt()


def test_curriculum_agent_builds_prompt(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    agent = CurriculumAgent()
    persona = PersonaProfile(
        audience_level="beginner",
        tone="friendly",
        prerequisites=[],
        learning_goals=["understand ownership"],
    )
    research = ResearchBrief(topic="Rust", findings=[], summary="Rust is a systems language.")
    prompt = agent.build_user_prompt(persona=persona, research=research)
    assert "beginner" in prompt
    assert "systems language" in prompt


def test_notebook_agent_requires_curriculum(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    agent = NotebookAgent()
    with pytest.raises(ValueError, match="curriculum"):
        agent.build_user_prompt()


def test_notebook_agent_defaults_to_first_lesson(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    agent = NotebookAgent()
    course = CourseOutline(
        course_title="Rust Basics",
        lessons=[
            Lesson(title="Ownership", objectives=["explain ownership"], estimated_minutes=30),
            Lesson(title="Borrowing", objectives=["explain borrowing"], estimated_minutes=30),
        ],
    )
    prompt = agent.build_user_prompt(curriculum=course)
    assert "Ownership" in prompt
    assert "Borrowing" not in prompt


def test_notebook_agent_lesson_index_out_of_range_raises(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    agent = NotebookAgent()
    course = CourseOutline(
        course_title="Rust Basics",
        lessons=[Lesson(title="Ownership", objectives=["x"], estimated_minutes=30)],
    )
    with pytest.raises(ValueError, match="out of range"):
        agent.build_user_prompt(curriculum=course, lesson_index=5)
