"""
Notebook agent - fourth stage of the pipeline.

Consumes the CourseOutline from the Curriculum agent and drafts notebook
cell content for one lesson. Built on LessonAgent (same base as the
Phase 3 content agents) so it automatically picks up persona-awareness
and consistent lesson-selection behavior rather than duplicating that
logic. Phase 2 scope: draft cell content only (this agent's job is
content, not file format). Looping over every lesson and real .ipynb
(nbformat) export both land in Phase 5.
"""

from __future__ import annotations

from agents.base import register_agent
from agents.lesson_agent_base import LessonAgent
from models.schemas import NotebookDraft
from prompts.notebook_prompt import NOTEBOOK_SYSTEM_PROMPT


@register_agent("notebook")
class NotebookAgent(LessonAgent):
    name = "notebook"
    system_prompt = NOTEBOOK_SYSTEM_PROMPT
    response_model = NotebookDraft
