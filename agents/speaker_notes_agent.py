"""Speaker Notes agent - generates an instructor script for a lesson."""

from __future__ import annotations

from agents.base import register_agent
from agents.lesson_agent_base import LessonAgent
from models.schemas import SpeakerNotes
from prompts.speaker_notes_prompt import SPEAKER_NOTES_SYSTEM_PROMPT


@register_agent("speaker_notes")
class SpeakerNotesAgent(LessonAgent):
    name = "speaker_notes"
    system_prompt = SPEAKER_NOTES_SYSTEM_PROMPT
    response_model = SpeakerNotes
