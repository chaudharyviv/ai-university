"""
Reviewer agent - Phase 4.

Unlike every other agent, this one isn't run as a normal pipeline step
via the agent registry chain - it's invoked directly by the Orchestrator
against another agent's output (see Orchestrator._run_with_review).
It's still registered under "reviewer" so it's visible on the Agents
Status page and independently testable, but selecting it on its own
from the Run Course page won't do anything useful since it needs
target_agent_name/target_output passed explicitly, not pulled from the
normal pipeline context.
"""

from __future__ import annotations

import json
from typing import Any

from agents.base import BaseAgent, register_agent
from models.schemas import ReviewVerdict
from prompts.reviewer_prompt import REVIEWER_SYSTEM_PROMPT


@register_agent("reviewer")
class ReviewerAgent(BaseAgent):
    name = "reviewer"
    system_prompt = REVIEWER_SYSTEM_PROMPT
    response_model = ReviewVerdict

    def build_user_prompt(self, **kwargs: Any) -> str:
        target_agent_name = kwargs.get("target_agent_name")
        target_output = kwargs.get("target_output")
        if target_agent_name is None or target_output is None:
            raise ValueError(
                "ReviewerAgent requires 'target_agent_name' and 'target_output' "
                "(it reviews another agent's output - it's not meant to be run "
                "standalone from the pipeline context)"
            )

        prompt = (
            f"Content type: {target_agent_name}\n\n"
            f"Generated content:\n{json.dumps(target_output.model_dump(), indent=2)}"
        )

        lesson = kwargs.get("lesson")
        if lesson is not None:
            prompt += f"\n\nLesson this should serve:\n{json.dumps(lesson.model_dump(), indent=2)}"

        persona = kwargs.get("persona")
        if persona is not None:
            prompt += f"\n\nTarget audience:\n{json.dumps(persona.model_dump(), indent=2)}"

        return prompt
