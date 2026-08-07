from types import SimpleNamespace

import pytest

import agents  # noqa: F401 - triggers agent registration
from agents.base import AgentResult, list_registered_agents
from agents.orchestrator import REVIEWABLE_AGENTS, Orchestrator, PipelineRun, sort_by_pipeline_order
from agents.reviewer_agent import ReviewerAgent
from config import settings
from models.schemas import CourseOutline, Lesson, PersonaProfile, ReviewVerdict


# --- ReviewerAgent unit tests -------------------------------------------------


def test_reviewer_requires_target(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    agent = ReviewerAgent()
    with pytest.raises(ValueError, match="target_agent_name"):
        agent.build_user_prompt()


def test_reviewer_builds_prompt_with_lesson_and_persona(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    agent = ReviewerAgent()
    target = SimpleNamespace(model_dump=lambda: {"lesson_title": "x", "questions": []})
    lesson = Lesson(title="Ownership", objectives=["explain it"], estimated_minutes=20)
    persona = PersonaProfile(
        audience_level="beginner", tone="friendly", prerequisites=[], learning_goals=["x"]
    )
    prompt = agent.build_user_prompt(
        target_agent_name="quiz", target_output=target, lesson=lesson, persona=persona
    )
    assert "quiz" in prompt
    assert "Ownership" in prompt
    assert "beginner" in prompt


def test_reviewer_registered_and_excluded_from_reviewable_set():
    assert "reviewer" in list_registered_agents()
    assert "reviewer" not in REVIEWABLE_AGENTS


def test_reviewer_appended_at_end_by_sort_order():
    # "reviewer" isn't in DEFAULT_PIPELINE_ORDER since it's not a normal
    # pipeline step - confirm the sort helper still handles it gracefully
    # rather than raising or silently dropping it.
    result = sort_by_pipeline_order(["reviewer", "persona"])
    assert result == ["persona", "reviewer"]


# --- Orchestrator review-loop tests (mocked, no live API calls) --------------


class _FakeContentAgent:
    """Stands in for any reviewable content agent (e.g. QuizAgent)."""

    def __init__(self):
        self.calls = 0

    def run(self, **kwargs):
        self.calls += 1
        return AgentResult(
            agent_name="quiz",
            success=True,
            output=SimpleNamespace(model_dump=lambda: {"lesson_title": "x", "questions": []}),
            model_used="test-model",
            estimated_cost_usd=0.01,
        )


def _make_fake_reviewer(verdicts: list[bool]):
    """Returns a fake ReviewerAgent class that yields the given approved/
    rejected sequence across successive .run() calls (repeats the last
    value if called more times than the list has entries)."""

    class _FakeReviewer:
        calls = 0

        def run(self, **kwargs):
            idx = min(_FakeReviewer.calls, len(verdicts) - 1)
            approved = verdicts[idx]
            _FakeReviewer.calls += 1
            return AgentResult(
                agent_name="reviewer",
                success=True,
                output=ReviewVerdict(
                    approved=approved,
                    feedback="looks good" if approved else "fix the answer key",
                    issues=[] if approved else ["wrong correct_answer_index"],
                ),
                model_used="test-model",
                estimated_cost_usd=0.005,
            )

    return _FakeReviewer


def test_run_with_review_approved_on_first_try(monkeypatch):
    monkeypatch.setattr("agents.reviewer_agent.ReviewerAgent", _make_fake_reviewer([True]))
    orch = Orchestrator()
    agent = _FakeContentAgent()

    result = orch._run_with_review("quiz", agent, {"topic": "x"}, PipelineRun(run_id="test"))

    assert result.success
    assert agent.calls == 1
    assert result.metadata["review_attempts"] == 0
    assert len(result.metadata["review_history"]) == 1
    assert result.metadata["review_history"][0]["approved"] is True
    assert result.estimated_cost_usd == pytest.approx(0.01 + 0.005)


def test_run_with_review_retries_then_approves(monkeypatch):
    monkeypatch.setattr("agents.reviewer_agent.ReviewerAgent", _make_fake_reviewer([False, True]))
    orch = Orchestrator()
    agent = _FakeContentAgent()

    result = orch._run_with_review("quiz", agent, {"topic": "x"}, PipelineRun(run_id="test"))

    assert result.success
    assert agent.calls == 2  # initial attempt + 1 revision
    assert result.metadata["review_attempts"] == 1
    assert len(result.metadata["review_history"]) == 2
    assert result.metadata["review_history"][-1]["approved"] is True
    # 2 content-generation calls + 2 reviewer calls, all at their stub costs
    assert result.estimated_cost_usd == pytest.approx(0.01 * 2 + 0.005 * 2)


def test_run_with_review_stops_at_max_attempts_and_keeps_last_output(monkeypatch):
    monkeypatch.setattr("agents.reviewer_agent.ReviewerAgent", _make_fake_reviewer([False]))
    orch = Orchestrator()
    agent = _FakeContentAgent()

    result = orch._run_with_review("quiz", agent, {"topic": "x"}, PipelineRun(run_id="test"))

    # Never approved, so it stops exactly at review_max_attempts rejections
    # without generating a call beyond that ceiling.
    assert result.success  # last generation attempt still succeeded, just unapproved
    assert agent.calls == settings.review_max_attempts
    assert result.metadata["review_attempts"] == settings.review_max_attempts
    assert all(not v["approved"] for v in result.metadata["review_history"])


def test_extract_lesson_defaults_to_first_lesson():
    course = CourseOutline(
        course_title="Rust",
        lessons=[
            Lesson(title="Ownership", objectives=["a"], estimated_minutes=20),
            Lesson(title="Borrowing", objectives=["b"], estimated_minutes=20),
        ],
    )
    lesson = Orchestrator._extract_lesson({"curriculum": course})
    assert lesson.title == "Ownership"


def test_extract_lesson_respects_lesson_index():
    course = CourseOutline(
        course_title="Rust",
        lessons=[
            Lesson(title="Ownership", objectives=["a"], estimated_minutes=20),
            Lesson(title="Borrowing", objectives=["b"], estimated_minutes=20),
        ],
    )
    lesson = Orchestrator._extract_lesson({"curriculum": course, "lesson_index": 1})
    assert lesson.title == "Borrowing"


def test_extract_lesson_returns_none_without_curriculum():
    assert Orchestrator._extract_lesson({"topic": "x"}) is None


# --- Cost-ceiling-inside-the-loop tests (red-team fix) -----------------------


def test_run_with_review_stops_mid_loop_when_run_already_near_ceiling(monkeypatch):
    # Simulates prior agents in the run having already spent close to the
    # ceiling - the review loop should refuse to even attempt review once
    # the initial generation call would push the run over budget, rather
    # than running the full generation+review+revision cycle first and
    # only checking afterward.
    monkeypatch.setattr(settings, "max_cost_per_run_usd", 0.005)
    monkeypatch.setattr("agents.reviewer_agent.ReviewerAgent", _make_fake_reviewer([True]))

    orch = Orchestrator()
    agent = _FakeContentAgent()  # costs 0.01 per call, already over the 0.005 ceiling
    run = PipelineRun(run_id="test")
    run.total_cost_usd = 0.0

    result = orch._run_with_review("quiz", agent, {"topic": "x"}, run)

    assert agent.calls == 1  # generated once, but review was skipped
    assert result.metadata["review_attempts"] == 0
    assert result.metadata["review_history"] == []


def test_run_with_review_stops_partway_through_revision_cycle_when_ceiling_hit(monkeypatch):
    # Ceiling allows the first generation + first review, but not a second
    # full cycle - the loop should stop after detecting this rather than
    # running every attempt and only checking the total once at the end.
    monkeypatch.setattr(settings, "max_cost_per_run_usd", 0.02)  # allows ~1 gen + 1 review
    monkeypatch.setattr("agents.reviewer_agent.ReviewerAgent", _make_fake_reviewer([False, True]))

    orch = Orchestrator()
    agent = _FakeContentAgent()  # 0.01/call
    run = PipelineRun(run_id="test")
    run.total_cost_usd = 0.0

    result = orch._run_with_review("quiz", agent, {"topic": "x"}, run)

    # First generation (0.01) + first review (0.005) = 0.015, under 0.02.
    # Rejected -> triggers a second generation call (cost isn't knowable
    # until after the call completes), which lands at 0.025 - over the
    # ceiling - so the loop stops there rather than also calling the
    # reviewer a second time.
    assert agent.calls == 2
    assert result.estimated_cost_usd == pytest.approx(0.01 + 0.005 + 0.01)


def test_run_with_review_uses_running_total_from_prior_agents(monkeypatch):
    # A run that already spent most of its budget on earlier agents
    # (persona, research, curriculum) should immediately skip review on
    # a reviewable agent rather than only noticing after spending more.
    monkeypatch.setattr(settings, "max_cost_per_run_usd", 0.1)
    monkeypatch.setattr("agents.reviewer_agent.ReviewerAgent", _make_fake_reviewer([True]))

    orch = Orchestrator()
    agent = _FakeContentAgent()
    run = PipelineRun(run_id="test")
    run.total_cost_usd = 0.095  # already close to the 0.1 ceiling from prior agents

    result = orch._run_with_review("quiz", agent, {"topic": "x"}, run)

    assert agent.calls == 1
    assert result.metadata["review_attempts"] == 0
    assert result.metadata["review_history"] == []


# --- Reviewer model separation (red-team fix) ---------------------------------


def test_reviewer_uses_distinct_model_from_default_generator():
    # The Reviewer must not silently share settings.primary_model - that
    # defeats the purpose of an independent review (a model grading its
    # own homework shares its own blind spots).
    assert ReviewerAgent.preferred_model != settings.primary_model
    assert ReviewerAgent.preferred_model == settings.reviewer_model
