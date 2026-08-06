"""
Web search tool.

Backed by Tavily when TAVILY_API_KEY is configured. Falls back to a
clearly-labeled stub result (not an exception) if the key is missing or
the Tavily call itself fails - a broken search tool shouldn't take down
the whole Research agent, it should just make the gap visible in the
logs and in the result content.
"""

from __future__ import annotations

from loguru import logger

from config import settings

_client = None  # lazy singleton - avoids constructing a TavilyClient at import time


def _get_client():
    global _client
    if _client is None:
        from tavily import TavilyClient

        _client = TavilyClient(api_key=settings.tavily_api_key)
    return _client


def _stub_result(query: str, reason: str) -> list[dict[str, str]]:
    logger.warning("web_search() falling back to stub for query {!r}: {}", query, reason)
    return [
        {
            "title": f"[STUB RESULT] {query}",
            "url": "https://example.com/stub-result",
            "snippet": f"Real web search unavailable ({reason}). This is placeholder data.",
        }
    ]


def web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """
    Search the web for `query` via Tavily and return up to `max_results`
    results.

    Returns:
        List of dicts with keys: title, url, snippet. Falls back to a
        single clearly-labeled stub result (never raises) if no Tavily
        key is configured or the API call fails, so a search outage
        degrades the Research agent's quality rather than crashing it.
    """
    if not settings.tavily_api_key:
        return _stub_result(query, "no TAVILY_API_KEY configured")

    try:
        client = _get_client()
        response = client.search(query=query, max_results=max_results, search_depth="basic")
    except Exception as exc:  # noqa: BLE001 - any Tavily/network failure degrades to stub
        return _stub_result(query, f"Tavily call failed: {exc}")

    raw_results = response.get("results", [])
    if not raw_results:
        return _stub_result(query, "Tavily returned no results")

    results = [
        {
            "title": r.get("title", "") or "(untitled)",
            "url": r.get("url", ""),
            "snippet": r.get("content", "") or "",
        }
        for r in raw_results[:max_results]
    ]
    logger.info("web_search(): {} real result(s) for query {!r}", len(results), query)
    return results
