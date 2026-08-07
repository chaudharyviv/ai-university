"""
Fixed persona archetypes for the hybrid persona approach.

audience_level and tone are hardcoded here and never touched by the LLM
- that's the whole point (reproducibility). prerequisites and
learning_goals are still generated per-topic by PersonaAgent, since
those genuinely should vary by topic even within a fixed archetype
("prerequisites for a K-12 Student learning fractions" is legitimately
different from "...learning Python").

"Custom" is not listed here - it's the sentinel meaning "fall back to
fully LLM-inferred persona," handled in PersonaAgent, not a real archetype.
"""

from __future__ import annotations

PERSONA_ARCHETYPES: dict[str, dict[str, str]] = {
    "K-12 Student": {
        "audience_level": "complete beginner, no assumed math or CS background, up to age 18",
        "tone": "playful, encouraging, and full of everyday analogies",
    },
    "College Student": {
        "audience_level": "has some foundational background but is still learning fundamentals",
        "tone": "clear, structured, and textbook-adjacent",
    },
    "Working Professional": {
        "audience_level": "practical and outcome-focused, not a technical specialist in this area",
        "tone": "direct, business-relevant, no patience for theory-first explanations",
    },
    "AI/Software Engineer": {
        "audience_level": "strong technical background, comfortable with jargon, math, and code",
        "tone": "terse and technical, assumes fluency",
    },
    "Career Switcher": {
        "audience_level": "motivated adult learner, genuinely new to this specific domain",
        "tone": "patient and encouraging but not condescending, grounded in real-world relevance",
    },
}

CUSTOM_ARCHETYPE = "Custom"

PERSONA_ARCHETYPE_OPTIONS: list[str] = [CUSTOM_ARCHETYPE, *PERSONA_ARCHETYPES.keys()]
