"""
Orchestrator - minimal Phase 1 stub.

Phase 1 scope: run a linear sequence of agents by name, accumulate
their results, enforce the cost ceiling, and return a run summary.

Phase 2+ will add: the real agent chain (persona -> research ->
curriculum -> notebook), parallel branches where safe, and richer
run-state persistence. The interface here (`Orchestrator.run_pipeline`)
is written to stay stable as that logic is filled in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from agents.base import AgentResult, get_agent_class
from config import settings
from tools.filesystem import get_run_dir, new_run_id

# Canonical dependency order. Agents not listed here are appended after,
# in whatever order they were passed in - update this list as new agents
# are registered in later phases.
# Phase 3 agents (code/diagram/quiz/assignment/speaker_notes) all depend
# only on "curriculum", not on each other or on "notebook" - they're
# listed after notebook here just to match the original phase-plan order,
# not because of a real dependency.
DEFAULT_PIPELINE_ORDER: list[str] = [
    "persona",
    "research",
    "curriculum",
    "notebook",
    "code",
    "diagram",
    "quiz",
    "assignment",
    "speaker_notes",
]

# Agents whose output the Reviewer agent checks (Phase 4). All of them
# take a single lesson from the curriculum, so a lesson + persona can
# always be attached to the review. "reviewer" itself is deliberately
# excluded - it doesn't review its own output.
REVIEWABLE_AGENTS: set[str] = {
    "notebook",
    "code",
    "diagram",
    "quiz",
    "assignment",
    "speaker_notes",
}


def sort_by_pipeline_order(agent_names: list[str]) -> list[str]:
    """
    Reorder an arbitrary list of agent names into dependency-safe order.

    Streamlit's multiselect returns items in click order, not list order,
    and the registry lists agents alphabetically - neither is safe to
    execute directly. This guarantees a consistent, dependency-correct
    order no matter how `agent_names` was produced.
    """
    known = [a for a in DEFAULT_PIPELINE_ORDER if a in agent_names]
    unknown = [a for a in agent_names if a not in DEFAULT_PIPELINE_ORDER]
    return known + unknown


@dataclass
class PipelineRun:
    run_id: str
    results: list[AgentResult] = field(default_factory=list)
    total_cost_usd: float = 0.0
    stopped_early: bool = False
    stop_reason: str | None = None
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return not self.stopped_early and all(r.success for r in self.results)


class Orchestrator:
    """Runs a named sequence of agents against a shared context dict."""

    def run_pipeline(
        self,
        agent_names: list[str],
        initial_context: dict[str, Any] | None = None,
        run_id: str | None = None,
        enable_review: bool | None = None,
    ) -> PipelineRun:
        """
        Run each agent in `agent_names`, in order.

        Each agent's `output` is merged into the shared context under a
        key matching the agent's name, so later agents can reference
        earlier agents' output (e.g. CurriculumAgent reading
        context["research"]).

        For agents in REVIEWABLE_AGENTS (Phase 4), the Reviewer agent
        checks the output; if rejected, the producing agent is re-run
        with the reviewer's feedback, up to settings.review_max_attempts
        times, before the last output is accepted as-is.

        Stops early if the running cost total would exceed
        settings.max_cost_per_run_usd, or if an agent fails and has no
        declared fallback behavior (always stop on failure - retry/skip
        policies for non-review failures are a later-phase concern).
        """
        run_id = run_id or new_run_id()
        enable_review = settings.enable_review if enable_review is None else enable_review
        agent_names = sort_by_pipeline_order(agent_names)
        get_run_dir(run_id)  # ensure workspace exists
        context: dict[str, Any] = dict(initial_context or {})
        run = PipelineRun(run_id=run_id)

        logger.info(
            "Starting pipeline run {} with agents (dependency order): {} (review={})",
            run_id,
            agent_names,
            enable_review,
        )

        for agent_name in agent_names:
            agent_cls = get_agent_class(agent_name)
            agent = agent_cls()

            if enable_review and agent_name in REVIEWABLE_AGENTS:
                result = self._run_with_review(agent_name, agent, context)
            else:
                result = agent.run(**context)

            run.results.append(result)
            run.total_cost_usd += result.estimated_cost_usd

            if run.total_cost_usd > settings.max_cost_per_run_usd:
                run.stopped_early = True
                run.stop_reason = (
                    f"Cost ceiling exceeded: ${run.total_cost_usd:.4f} > "
                    f"${settings.max_cost_per_run_usd:.2f}"
                )
                logger.warning("Run {} stopped: {}", run_id, run.stop_reason)
                break

            if not result.success:
                run.stopped_early = True
                run.stop_reason = f"Agent {agent_name!r} failed: {result.error}"
                logger.warning("Run {} stopped: {}", run_id, run.stop_reason)
                break

            context[agent_name] = result.output

        run.context = context

        logger.info(
            "Pipeline run {} finished. success={} total_cost=${:.4f}",
            run_id,
            run.success,
            run.total_cost_usd,
        )
        return run

    @staticmethod
    def _extract_lesson(context: dict[str, Any]) -> Any | None:
        """Pull the lesson a reviewable agent was generating content for,
        so the Reviewer can judge fit against it. Mirrors LessonAgent's
        own default-to-first-lesson behavior."""
        course = context.get("curriculum")
        if course is None or not course.lessons:
            return None
        lesson_index = context.get("lesson_index", 0)
        if lesson_index >= len(course.lessons):
            lesson_index = 0
        return course.lessons[lesson_index]

    def _run_with_review(self, agent_name: str, agent: Any, context: dict[str, Any]) -> AgentResult:
        """
        Run `agent`, then have the Reviewer agent check its output.
        If rejected, re-run `agent` with the reviewer's feedback, up to
        settings.review_max_attempts times.

        Returns the final AgentResult with combined cost across every
        generation + review call, and review history recorded in
        `result.metadata["review_history"]` for the UI to display.
        """
        # Local import avoids a module-level circular import between
        # orchestrator.py and reviewer_agent.py.
        from agents.reviewer_agent import ReviewerAgent

        reviewer = ReviewerAgent()
        lesson = self._extract_lesson(context)
        persona = context.get("persona")

        result = agent.run(**context)
        total_cost = result.estimated_cost_usd
        review_history: list[dict[str, Any]] = []

        attempt = 0
        while result.success and attempt < settings.review_max_attempts:
            review_result = reviewer.run(
                target_agent_name=agent_name,
                target_output=result.output,
                lesson=lesson,
                persona=persona,
            )
            total_cost += review_result.estimated_cost_usd

            if not review_result.success:
                # Reviewer itself couldn't produce a valid verdict - accept
                # the content as-is rather than looping on a broken reviewer.
                logger.warning(
                    "{}: reviewer failed to produce a verdict ({}), accepting content as-is",
                    agent_name,
                    review_result.error,
                )
                break

            verdict = review_result.output
            review_history.append(verdict.model_dump())

            if verdict.approved:
                logger.info("{}: approved by reviewer after {} attempt(s)", agent_name, attempt + 1)
                break

            attempt += 1
            if attempt >= settings.review_max_attempts:
                logger.warning(
                    "{}: reviewer requested revision but max attempts ({}) reached; keeping last output",
                    agent_name,
                    settings.review_max_attempts,
                )
                break

            logger.info(
                "{}: reviewer requested revision (attempt {}/{}): {}",
                agent_name,
                attempt,
                settings.review_max_attempts,
                verdict.feedback,
            )
            result = agent.run(
                **context,
                revision_feedback=verdict.feedback,
                previous_output=result.output.model_dump(),
            )
            total_cost += result.estimated_cost_usd

        result.estimated_cost_usd = total_cost
        result.metadata = {
            **result.metadata,
            "review_history": review_history,
            "review_attempts": attempt,
        }
        return result
