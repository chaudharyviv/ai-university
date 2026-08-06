"""
Web search tool - STUB for Phase 1.

The Research agent (Phase 2) will call `web_search()`. For now this
returns a clearly-labeled placeholder so the rest of the pipeline
(orchestrator, logging, cost tracking) can be built and tested without
burning API calls or requiring a Tavily key yet.

Replace the body of `web_search()` with a real Tavily/Serper call in
Phase 2 - the function signature is intentionally final so nothing
else needs to change when that happens.
"""

from __future__ import annotations

from loguru import logger


def web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """
    Search the web for `query` and return up to `max_results` results.

    Returns:
        List of dicts with keys: title, url, snippet.

    NOTE: Phase 1 stub. Always returns a placeholder result so callers
    can be built/tested against the real interface shape.
    """
    logger.warning(
        "web_search() is a Phase 1 stub - returning placeholder data for query: {!r}",
        query,
    )
    return [
        {
            "title": f"[STUB RESULT] {query}",
            "url": "https://example.com/stub-result",
            "snippet": (
                "This is placeholder data from the Phase 1 search stub. "
                "Real web search (Tavily) is wired up in Phase 2."
            ),
        }
    ][:max_results]
