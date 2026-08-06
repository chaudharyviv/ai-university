"""Assignment agent - generates a homework assignment for a lesson."""

from __future__ import annotations

from agents.base import register_agent
from agents.lesson_agent_base import LessonAgent
from models.schemas import Assignment
from prompts.assignment_prompt import ASSIGNMENT_SYSTEM_PROMPT


@register_agent("assignment")
class AssignmentAgent(LessonAgent):
    name = "assignment"
    system_prompt = ASSIGNMENT_SYSTEM_PROMPT
    response_model = Assignment
