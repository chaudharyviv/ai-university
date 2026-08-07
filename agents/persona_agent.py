"""
Persona agent - first stage of the pipeline.

Takes a raw course `topic` string and produces a `PersonaProfile`
(audience level, tone, prerequisites, learning goals) that every
downstream agent designs around.

Hybrid persona (see models/persona_archetypes.py): if a
`persona_archetype` is passed in context and isn't "Custom",
audience_level/tone come from the fixed archetype (never touched by the
LLM, for reproducibility), while prerequisites/learning_goals are still
generated per-topic. If no archetype is given, or it's "Custom", the
LLM generates the full profile as before.
"""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent, register_agent
from models.persona_archetypes import CUSTOM_ARCHETYPE, PERSONA_ARCHETYPES
from models.schemas import PersonaEssentials, PersonaProfile
from prompts.persona_prompt import PERSONA_ESSENTIALS_SYSTEM_PROMPT, PERSONA_SYSTEM_PROMPT


@register_agent("persona")
class PersonaAgent(BaseAgent):
    name = "persona"
    system_prompt = PERSONA_SYSTEM_PROMPT
    response_model = PersonaProfile

    def _active_archetype(self, **kwargs: Any) -> dict[str, str] | None:
        archetype_name = kwargs.get("persona_archetype")
        if not archetype_name or archetype_name == CUSTOM_ARCHETYPE:
            return None
        if archetype_name not in PERSONA_ARCHETYPES:
            raise ValueError(
                f"Unknown persona_archetype {archetype_name!r}. "
                f"Valid options: {[CUSTOM_ARCHETYPE, *PERSONA_ARCHETYPES]}"
            )
        return PERSONA_ARCHETYPES[archetype_name]

    def build_user_prompt(self, **kwargs: Any) -> str:
        topic = kwargs.get("topic")
        if not topic:
            raise ValueError("PersonaAgent requires a 'topic' in context")

        archetype = self._active_archetype(**kwargs)
        if archetype is None:
            return f"Course topic: {topic}"

        return (
            f"Course topic: {topic}\n\n"
            f"Fixed target audience: {archetype['audience_level']}\n"
            f"Fixed teaching tone: {archetype['tone']}\n\n"
            "Generate only the prerequisites and learning goals that fit "
            "this topic for this audience - do not restate or redefine "
            "the audience/tone above."
        )

    def run(self, **kwargs: Any) -> Any:
        archetype_name = kwargs.get("persona_archetype")
        archetype = self._active_archetype(**kwargs)

        if archetype is None:
            # Custom / no archetype given - unchanged full-generation path.
            self.system_prompt = PERSONA_SYSTEM_PROMPT
            self.response_model = PersonaProfile
            return super().run(**kwargs)

        # Fixed-archetype path: LLM only fills prerequisites/learning_goals.
        self.system_prompt = PERSONA_ESSENTIALS_SYSTEM_PROMPT
        self.response_model = PersonaEssentials
        result = super().run(**kwargs)

        if result.success:
            essentials: PersonaEssentials = result.output
            result.output = PersonaProfile(
                audience_level=archetype["audience_level"],
                tone=archetype["tone"],
                prerequisites=essentials.prerequisites,
                learning_goals=essentials.learning_goals,
            )
            result.metadata = {**result.metadata, "persona_archetype": archetype_name}

        return result
