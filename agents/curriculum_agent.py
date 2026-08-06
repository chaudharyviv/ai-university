"""
Curriculum agent - third stage of the pipeline.

Consumes the Persona profile and Research brief, produces a CourseOutline
(ordered lessons with objectives) that the Notebook agent (and Phase 3's
content-generation agents) build from.
"""

from __future__ import annotations

import json
from typing import Any

from agents.base import BaseAgent, register_agent
from models.schemas import CourseOutline
from prompts.curriculum_prompt import CURRICULUM_SYSTEM_PROMPT


@register_agent("curriculum")
class CurriculumAgent(BaseAgent):
    name = "curriculum"
    system_prompt = CURRICULUM_SYSTEM_PROMPT
    response_model = CourseOutline

    def build_user_prompt(self, **kwargs: Any) -> str:
        persona = kwargs.get("persona")
        research = kwargs.get("research")
        if persona is None or research is None:
            raise ValueError(
                "CurriculumAgent requires 'persona' and 'research' in context "
                "(run the persona and research agents first)"
            )

        return (
            f"Persona:\n{json.dumps(persona.model_dump(), indent=2)}\n\n"
            f"Research brief:\n{json.dumps(research.model_dump(), indent=2)}"
        )
