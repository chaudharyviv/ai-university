"""
Notebook export - turns agent output into a real .ipynb file via nbformat.

Consumes NotebookDraft (the primary content) and optionally folds in
CodeExerciseSet, DiagramSet, Quiz, and Assignment as extra sections, so
one .ipynb ends up as the complete lesson package rather than five
separate documents.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from loguru import logger

from models.schemas import Assignment, CodeExerciseSet, DiagramSet, NotebookDraft, Quiz


def _markdown_cell(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text)


def _code_cell(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text)


def build_notebook(
    draft: NotebookDraft,
    *,
    code_exercises: CodeExerciseSet | None = None,
    diagrams: DiagramSet | None = None,
    quiz: Quiz | None = None,
    assignment: Assignment | None = None,
) -> nbf.NotebookNode:
    """Assemble a full nbformat notebook from one or more agents' output."""
    nb = nbf.v4.new_notebook()
    cells: list[nbf.NotebookNode] = []

    # --- Core lesson content (NotebookAgent) ---
    for cell in draft.cells:
        if cell.cell_type == "code":
            cells.append(_code_cell(cell.content))
        else:
            cells.append(_markdown_cell(cell.content))

    # --- Diagrams (DiagramAgent) - included as fenced Mermaid blocks.
    # Rendering requires a Mermaid-aware viewer (e.g. JupyterLab with the
    # mermaid extension, or GitHub's notebook renderer); plain nbconvert
    # HTML/PDF will show the raw code block, not a rendered diagram.
    if diagrams and diagrams.diagrams:
        cells.append(_markdown_cell("## Diagrams"))
        for d in diagrams.diagrams:
            cells.append(_markdown_cell(f"**{d.title}**\n\n{d.description}\n\n```mermaid\n{d.mermaid_code}\n```"))

    # --- Practice exercises (CodeAgent) - starter code as a runnable cell,
    # solution hidden behind a <details> block so it doesn't spoil the
    # exercise on first read.
    if code_exercises and code_exercises.exercises:
        cells.append(_markdown_cell("## Exercises"))
        for i, ex in enumerate(code_exercises.exercises, start=1):
            cells.append(_markdown_cell(f"**Exercise {i}:** {ex.prompt}"))
            cells.append(_code_cell(ex.starter_code))
            cells.append(
                _markdown_cell(
                    f"<details><summary>Solution</summary>\n\n```python\n{ex.solution_code}\n```\n</details>"
                )
            )

    # --- Quiz (QuizAgent) - questions visible, answer key hidden.
    if quiz and quiz.questions:
        cells.append(_markdown_cell("## Quiz"))
        for i, q in enumerate(quiz.questions, start=1):
            options_md = "\n".join(f"- {opt}" for opt in q.options)
            cells.append(_markdown_cell(f"**Q{i}.** {q.question}\n\n{options_md}"))
        answer_key = "\n".join(
            f"{i}. **{chr(65 + q.correct_answer_index)}** - {q.explanation}"
            for i, q in enumerate(quiz.questions, start=1)
        )
        cells.append(_markdown_cell(f"<details><summary>Answer key</summary>\n\n{answer_key}\n</details>"))

    # --- Assignment (AssignmentAgent) ---
    if assignment:
        deliverables_md = "\n".join(f"- {d}" for d in assignment.deliverables)
        rubric_md = "\n".join(f"- {r}" for r in assignment.rubric)
        cells.append(
            _markdown_cell(
                f"## Assignment: {assignment.title}\n\n"
                f"{assignment.instructions}\n\n"
                f"**Deliverables**\n{deliverables_md}\n\n"
                f"**Rubric**\n{rubric_md}"
            )
        )

    nb["cells"] = cells
    return nb


def export_notebook_to_file(nb: nbf.NotebookNode, path: Path) -> Path:
    """Validate and write a notebook to disk. Raises nbformat.ValidationError
    on a malformed notebook rather than writing a broken file silently."""
    nbf.validate(nb)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        nbf.write(nb, f)
    logger.info("Wrote notebook: {} ({} cells)", path, len(nb["cells"]))
    return path
