"""Quiz agent - generates multiple-choice questions for a lesson."""

from __future__ import annotations

from agents.base import register_agent
from agents.lesson_agent_base import LessonAgent
from models.schemas import Quiz
from prompts.quiz_prompt import QUIZ_SYSTEM_PROMPT


@register_agent("quiz")
class QuizAgent(LessonAgent):
    name = "quiz"
    system_prompt = QUIZ_SYSTEM_PROMPT
    response_model = Quiz
