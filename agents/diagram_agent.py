"""Diagram agent - generates Mermaid diagrams for a lesson's concepts."""

from __future__ import annotations

from agents.base import register_agent
from agents.lesson_agent_base import LessonAgent
from models.schemas import DiagramSet
from prompts.diagram_prompt import DIAGRAM_SYSTEM_PROMPT


@register_agent("diagram")
class DiagramAgent(LessonAgent):
    name = "diagram"
    system_prompt = DIAGRAM_SYSTEM_PROMPT
    response_model = DiagramSet
