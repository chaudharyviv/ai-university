"""
Persona agent - first stage of the pipeline.

Takes a raw course `topic` string and produces a `PersonaProfile`
(audience level, tone, prerequisites, learning goals) that every
downstream agent designs around.
"""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent, register_agent
from models.schemas import PersonaProfile
from prompts.persona_prompt import PERSONA_SYSTEM_PROMPT


@register_agent("persona")
class PersonaAgent(BaseAgent):
    name = "persona"
    system_prompt = PERSONA_SYSTEM_PROMPT
    response_model = PersonaProfile

    def build_user_prompt(self, **kwargs: Any) -> str:
        topic = kwargs.get("topic")
        if not topic:
            raise ValueError("PersonaAgent requires a 'topic' in context")
        return f"Course topic: {topic}"
