"""
Importing this package registers every concrete agent (via the
`@register_agent` decorator in each module) so `agents.base.get_agent_class`
and `list_registered_agents` work without callers needing to know which
modules exist. Add new agent modules to this list as they're built.
"""

from agents import (  # noqa: F401 - imported for registration side effects
    assignment_agent,
    code_agent,
    curriculum_agent,
    diagram_agent,
    notebook_agent,
    persona_agent,
    quiz_agent,
    research_agent,
    reviewer_agent,
    speaker_notes_agent,
)
