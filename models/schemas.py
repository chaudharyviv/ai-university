"""
Structured I/O schemas shared across agents.

Agents that need reliable, parseable output (not just free-text) validate
their LLM response against one of these. Keeping them here (rather than
inline in each agent) means the Orchestrator and UI can import a schema
without importing the agent that produces it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PersonaProfile(BaseModel):
    """Defines the target learner and teaching voice for a course."""

    audience_level: str = Field(description="e.g. 'complete beginner', 'working engineer'")
    tone: str = Field(description="e.g. 'friendly and encouraging', 'terse and technical'")
    prerequisites: list[str] = Field(default_factory=list)
    learning_goals: list[str] = Field(default_factory=list)


class ResearchFinding(BaseModel):
    title: str
    url: str
    key_points: list[str]


class ResearchBrief(BaseModel):
    """Output of the Research agent: what it found, ready for Curriculum to consume."""

    topic: str
    findings: list[ResearchFinding]
    summary: str


class Lesson(BaseModel):
    title: str
    objectives: list[str]
    estimated_minutes: int = 30


class CourseOutline(BaseModel):
    """Output of the Curriculum agent."""

    course_title: str
    lessons: list[Lesson]


class NotebookCell(BaseModel):
    cell_type: str = Field(description="'markdown' or 'code'")
    content: str


class NotebookDraft(BaseModel):
    """Output of the Notebook agent: cell-by-cell content, before nbformat export (Phase 5)."""

    lesson_title: str
    cells: list[NotebookCell]


# --- Phase 3: Content Generation Agents -------------------------------------


class CodeExercise(BaseModel):
    prompt: str = Field(description="The task the learner is asked to solve")
    starter_code: str
    solution_code: str


class CodeExerciseSet(BaseModel):
    """Output of the Code agent: standalone practice exercises for a lesson,
    distinct from the inline examples embedded in the Notebook draft."""

    lesson_title: str
    exercises: list[CodeExercise]


class DiagramSpec(BaseModel):
    title: str
    mermaid_code: str = Field(description="Valid Mermaid diagram syntax")
    description: str = Field(description="One sentence on what the diagram illustrates")


class DiagramSet(BaseModel):
    """Output of the Diagram agent."""

    lesson_title: str
    diagrams: list[DiagramSpec]


class QuizQuestion(BaseModel):
    question: str
    options: list[str] = Field(description="Exactly 4 options")
    correct_answer_index: int = Field(description="0-indexed position of the correct option")
    explanation: str = Field(description="Why the correct answer is correct")


class Quiz(BaseModel):
    """Output of the Quiz agent."""

    lesson_title: str
    questions: list[QuizQuestion]


class Assignment(BaseModel):
    """Output of the Assignment agent."""

    lesson_title: str
    title: str
    instructions: str
    deliverables: list[str]
    rubric: list[str] = Field(description="Grading criteria, one item per line")


class SpeakerNoteSection(BaseModel):
    section_title: str
    script: str = Field(description="What the instructor would actually say for this section")


class SpeakerNotes(BaseModel):
    """Output of the Speaker Notes agent."""

    lesson_title: str
    sections: list[SpeakerNoteSection]


# --- Phase 4: Quality & Validation -------------------------------------------


class ReviewVerdict(BaseModel):
    """Output of the Reviewer agent: a pass/fail judgment on another
    agent's content, with concrete feedback if it doesn't pass."""

    approved: bool
    feedback: str = Field(description="Concrete, actionable feedback - what's wrong and how to fix it")
    issues: list[str] = Field(
        default_factory=list, description="Short bullet list of specific problems found, empty if approved"
    )
