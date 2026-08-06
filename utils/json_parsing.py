"""
Helper for agents that ask the LLM to respond with a JSON object.

Models frequently wrap JSON in markdown code fences or add a stray
sentence despite instructions not to - this strips the common cases
before handing off to `pydantic.BaseModel.model_validate_json`.
"""

from __future__ import annotations

import json
import re

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_json(raw: str) -> dict:
    """
    Best-effort extraction of a JSON object from raw LLM text output.

    Raises json.JSONDecodeError if no valid JSON object can be found -
    callers should let that propagate into AgentResult.error rather than
    silently returning something malformed.
    """
    text = _FENCE_RE.sub("", raw).strip()

    # If there's leading/trailing prose around the object despite
    # instructions, fall back to grabbing the outermost {...}.
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]

    # strict=False allows raw control characters (literal newlines, tabs)
    # inside string values. This is technically invalid JSON, but LLMs
    # routinely emit unescaped newlines when a string value contains
    # multi-line code (e.g. NotebookDraft cell content) despite being
    # told to produce valid JSON - rejecting it would fail agents that
    # have otherwise done exactly what was asked.
    return json.loads(text, strict=False)
