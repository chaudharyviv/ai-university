import pytest

import agents  # noqa: F401 - triggers agent registration
from agents.assignment_agent import AssignmentAgent
from agents.base import list_registered_agents
from agents.code_agent import CodeAgent
from agents.diagram_agent import DiagramAgent
from agents.notebook_agent import NotebookAgent
from agents.orchestrator import DEFAULT_PIPELINE_ORDER, sort_by_pipeline_order
from agents.quiz_agent import QuizAgent
from agents.speaker_notes_agent import SpeakerNotesAgent
from models.schemas import CourseOutline, Lesson, PersonaProfile

PHASE3_AGENT_CLASSES = [CodeAgent, DiagramAgent, QuizAgent, AssignmentAgent, SpeakerNotesAgent]


def test_all_phase3_agents_registered():
    registered = set(list_registered_agents())
    assert {"code", "diagram", "quiz", "assignment", "speaker_notes"} <= registered


def test_default_pipeline_order_includes_all_content_agents():
    # "reviewer" (Phase 4) is registered but deliberately excluded from
    # DEFAULT_PIPELINE_ORDER - it's invoked by the orchestrator's review
    # loop, not run as a standalone pipeline step.
    non_reviewer_agents = set(list_registered_agents()) - {"reviewer"}
    assert set(DEFAULT_PIPELINE_ORDER) == non_reviewer_agents


@pytest.mark.parametrize("agent_cls", PHASE3_AGENT_CLASSES)
def test_lesson_agent_requires_curriculum(monkeypatch, agent_cls):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    agent = agent_cls()
    with pytest.raises(ValueError, match="curriculum"):
        agent.build_user_prompt()


@pytest.mark.parametrize("agent_cls", PHASE3_AGENT_CLASSES)
def test_lesson_agent_builds_prompt_from_first_lesson_by_default(monkeypatch, agent_cls):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    agent = agent_cls()
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


@pytest.mark.parametrize("agent_cls", PHASE3_AGENT_CLASSES)
def test_lesson_agent_respects_lesson_index(monkeypatch, agent_cls):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    agent = agent_cls()
    course = CourseOutline(
        course_title="Rust Basics",
        lessons=[
            Lesson(title="Ownership", objectives=["x"], estimated_minutes=30),
            Lesson(title="Borrowing", objectives=["y"], estimated_minutes=30),
        ],
    )
    prompt = agent.build_user_prompt(curriculum=course, lesson_index=1)
    assert "Borrowing" in prompt
    assert "Ownership" not in prompt


@pytest.mark.parametrize("agent_cls", PHASE3_AGENT_CLASSES)
def test_lesson_agent_includes_persona_when_present(monkeypatch, agent_cls):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    agent = agent_cls()
    course = CourseOutline(
        course_title="Rust Basics",
        lessons=[Lesson(title="Ownership", objectives=["x"], estimated_minutes=30)],
    )
    persona = PersonaProfile(
        audience_level="complete beginner",
        tone="friendly and encouraging",
        prerequisites=[],
        learning_goals=["understand ownership"],
    )
    prompt = agent.build_user_prompt(curriculum=course, persona=persona)
    assert "complete beginner" in prompt
    assert "friendly and encouraging" in prompt


@pytest.mark.parametrize("agent_cls", PHASE3_AGENT_CLASSES)
def test_lesson_agent_omits_persona_section_when_absent(monkeypatch, agent_cls):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    agent = agent_cls()
    course = CourseOutline(
        course_title="Rust Basics",
        lessons=[Lesson(title="Ownership", objectives=["x"], estimated_minutes=30)],
    )
    prompt = agent.build_user_prompt(curriculum=course)
    assert "Target audience" not in prompt


def test_notebook_agent_also_gets_persona(monkeypatch):
    # NotebookAgent predates LessonAgent's persona support - confirm the
    # refactor onto LessonAgent actually picked it up.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    agent = NotebookAgent()
    course = CourseOutline(
        course_title="Rust Basics",
        lessons=[Lesson(title="Ownership", objectives=["x"], estimated_minutes=30)],
    )
    persona = PersonaProfile(
        audience_level="senior engineer",
        tone="terse and technical",
        prerequisites=[],
        learning_goals=["understand ownership"],
    )
    prompt = agent.build_user_prompt(curriculum=course, persona=persona)
    assert "senior engineer" in prompt


def test_full_nine_agent_order_is_dependency_safe():
    scrambled = list(reversed(DEFAULT_PIPELINE_ORDER))
    assert sort_by_pipeline_order(scrambled) == DEFAULT_PIPELINE_ORDER
