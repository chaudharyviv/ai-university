"""
Run-level export - takes a finished pipeline run's context and produces
the final deliverables: a Jupyter notebook and a slide deck, zipped
together under `outputs/<run_id>/`.

This is deliberately NOT an LLM agent - export is a deterministic file-
generation step over already-generated content, so it runs as a plain
function the UI calls after a pipeline run finishes, not as a pipeline
step itself.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from loguru import logger

from config import settings
from tools.filesystem import validate_run_id
from tools.notebook_export import build_notebook, export_notebook_to_file
from tools.pptx_export import LessonExtras, build_pptx, export_pptx_to_file


def export_run(run_id: str, context: dict[str, Any]) -> Path:
    """
    Build course.ipynb + course_slides.pptx from a pipeline run's final
    context, write them to outputs/<run_id>/, zip that directory, and
    return the zip path.

    Raises ValueError if the context doesn't have the minimum required
    output (a CourseOutline from the curriculum agent) - export can't do
    anything meaningful without at least that.
    """
    run_id = validate_run_id(run_id)

    course = context.get("curriculum")
    if course is None:
        raise ValueError("Cannot export: no 'curriculum' output in context (run the curriculum agent first)")

    outputs_root = settings.outputs_dir.resolve()
    run_dir = (settings.outputs_dir / run_id).resolve()
    if outputs_root not in run_dir.parents and run_dir != outputs_root:
        raise ValueError(f"Invalid run_id {run_id!r}: path escapes outputs directory")
    run_dir.mkdir(parents=True, exist_ok=True)

    notebook_draft = context.get("notebook")
    if notebook_draft is not None:
        nb = build_notebook(
            notebook_draft,
            code_exercises=context.get("code"),
            diagrams=context.get("diagram"),
            quiz=context.get("quiz"),
            assignment=context.get("assignment"),
        )
        export_notebook_to_file(nb, run_dir / "course.ipynb")
    else:
        logger.warning("export_run({}): no 'notebook' output in context, skipping .ipynb export", run_id)

    # Phase 3/4 agents currently only produce content for lesson 0 (see
    # module docstrings), so that's the only lesson with rich extras.
    lesson_extras = {
        0: LessonExtras(
            diagrams=context.get("diagram"),
            quiz=context.get("quiz"),
            speaker_notes=context.get("speaker_notes"),
        )
    }
    prs = build_pptx(course, persona=context.get("persona"), lesson_extras=lesson_extras)
    export_pptx_to_file(prs, run_dir / "course_slides.pptx")

    zip_path = settings.outputs_dir / f"{run_id}.zip"
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", root_dir=run_dir)
    logger.info("Exported run {} to {}", run_id, zip_path)
    return zip_path
