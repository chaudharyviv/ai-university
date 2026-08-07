"""
Filesystem tool: manages the per-run workspace directory.

Every course-generation run gets its own subdirectory under
`settings.workspace_dir`, keyed by a run_id, so concurrent/past runs
never collide and cleanup is a single `rm -rf <run_dir>`.
"""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from loguru import logger

from config import settings

# Matches uuid.hex[:12]-style ids from new_run_id(); rejects path
# separators / traversal. Single source of truth - tools/export.py
# imports this rather than duplicating it, so the two can't drift.
_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def validate_run_id(run_id: str) -> str:
    if not _SAFE_RUN_ID.fullmatch(run_id):
        raise ValueError(
            f"Invalid run_id {run_id!r}: must be 1-64 chars of [A-Za-z0-9_-] "
            "(no path separators or '..')"
        )
    return run_id


def new_run_id() -> str:
    """Generate a short, sortable-ish run identifier."""
    return uuid.uuid4().hex[:12]


def get_run_dir(run_id: str, create: bool = True) -> Path:
    """
    Return the workspace directory for a given run_id.

    Args:
        run_id: identifier returned by `new_run_id()`.
        create: if True, create the directory (and parents) if missing.

    Raises ValueError if run_id isn't a safe path component (this used
    to be unvalidated here - export.py had the check, this didn't,
    which was an inconsistency: cleanup_run() could be handed a
    traversal payload with no guard).
    """
    run_id = validate_run_id(run_id)
    run_dir = settings.workspace_dir / run_id
    if create:
        run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_text_file(run_id: str, relative_path: str, content: str) -> Path:
    """
    Write a text file inside a run's workspace.

    `relative_path` may include subdirectories (e.g. "notebooks/lesson1.ipynb");
    they are created as needed. Refuses to write outside the run directory.
    """
    run_dir = get_run_dir(run_id)
    target = (run_dir / relative_path).resolve()

    if run_dir.resolve() not in target.parents and target != run_dir.resolve():
        raise ValueError(f"Refusing to write outside run directory: {relative_path!r}")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    logger.debug("Wrote {} bytes to {}", len(content), target)
    return target


def list_run_files(run_id: str) -> list[Path]:
    """List all files (not directories) currently in a run's workspace."""
    run_dir = get_run_dir(run_id, create=False)
    if not run_dir.exists():
        return []
    return sorted(p for p in run_dir.rglob("*") if p.is_file())


def cleanup_run(run_id: str) -> None:
    """Delete a run's entire workspace directory. Irreversible."""
    run_dir = get_run_dir(run_id, create=False)
    if run_dir.exists():
        shutil.rmtree(run_dir)
        logger.info("Cleaned up run workspace: {}", run_id)
