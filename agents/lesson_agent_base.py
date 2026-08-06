"""
Shared base for every Phase 3 content-generation agent.

Code, Diagram, Quiz, Assignment, and Speaker Notes all have the identical
input contract: they consume one lesson from the CourseOutline the
Curriculum agent produced. This factors that out so each concrete agent
file only has to declare its name/prompt/schema.
"""

from __future__ import annotations

import json
from typing import Any

from agents.base import BaseAgent


class LessonAgent(BaseAgent):
    """
    Base class for agents that generate content for a single lesson.

    Like NotebookAgent, defaults to the first lesson in the outline
    unless `lesson_index` is passed in context - looping over every
    lesson in one run is a Phase 4/5 concern, not Phase 3.
    """

    def build_user_prompt(self, **kwargs: Any) -> str:
        course = kwargs.get("curriculum")
        if course is None:
            raise ValueError(
                f"{self.__class__.__name__} requires 'curriculum' in context "
                "(run the curriculum agent first)"
            )

        lesson_index = kwargs.get("lesson_index", 0)
        if not course.lessons:
            raise ValueError("Curriculum has no lessons to generate content for")
        if lesson_index >= len(course.lessons):
            raise ValueError(
                f"lesson_index={lesson_index} out of range (course has {len(course.lessons)} lessons)"
            )

        lesson = course.lessons[lesson_index]
        prompt = f"Lesson:\n{json.dumps(lesson.model_dump(), indent=2)}"

        # Persona is optional in context (e.g. unit tests, or a pipeline run
        # that skipped the persona agent) - when present, every downstream
        # agent should match its audience level and tone rather than
        # producing generically-toned content regardless of who it's for.
        persona = kwargs.get("persona")
        if persona is not None:
            prompt += f"\n\nTarget audience:\n{json.dumps(persona.model_dump(), indent=2)}"

        # Set by Orchestrator._run_with_review (Phase 4) on a retry after
        # the Reviewer agent rejected the first attempt. Optional - a plain
        # first-time run never has these.
        revision_feedback = kwargs.get("revision_feedback")
        if revision_feedback:
            prompt += (
                f"\n\nA reviewer flagged issues with your previous attempt and "
                f"requested a revision:\n{revision_feedback}"
            )
            previous_output = kwargs.get("previous_output")
            if previous_output is not None:
                prompt += f"\n\nYour previous output was:\n{json.dumps(previous_output, indent=2)}"
            prompt += "\n\nProduce a revised version that addresses this feedback and still follows the required schema."

        return prompt
