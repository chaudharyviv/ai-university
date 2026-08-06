"""Code agent - generates standalone practice exercises for a lesson."""

from __future__ import annotations

from agents.base import register_agent
from agents.lesson_agent_base import LessonAgent
from models.schemas import CodeExerciseSet
from prompts.code_prompt import CODE_SYSTEM_PROMPT


@register_agent("code")
class CodeAgent(LessonAgent):
    name = "code"
    system_prompt = CODE_SYSTEM_PROMPT
    response_model = CodeExerciseSet
