"""
Tests for tools/search.py. No live Tavily calls - _get_client is
monkeypatched to a fake client so these run offline and free.
"""

from __future__ import annotations

from tools.search import web_search


class _FakeTavilyClient:
    def __init__(self, response: dict | None = None, raise_exc: Exception | None = None):
        self._response = response or {"results": []}
        self._raise_exc = raise_exc
        self.last_call_kwargs: dict | None = None

    def search(self, **kwargs):
        self.last_call_kwargs = kwargs
        if self._raise_exc:
            raise self._raise_exc
        return self._response


def test_web_search_returns_stub_when_no_api_key(monkeypatch):
    monkeypatch.setattr("tools.search.settings.tavily_api_key", "")
    results = web_search("large language models")
    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/stub-result"
    assert "TAVILY_API_KEY" in results[0]["snippet"]


def test_web_search_returns_real_results(monkeypatch):
    monkeypatch.setattr("tools.search.settings.tavily_api_key", "fake-key")
    fake_client = _FakeTavilyClient(
        response={
            "results": [
                {"title": "LLM Basics", "url": "https://example.com/llm-basics", "content": "LLMs predict tokens."},
                {"title": "Transformers Explained", "url": "https://example.com/transformers", "content": "Attention is key."},
            ]
        }
    )
    monkeypatch.setattr("tools.search._get_client", lambda: fake_client)

    results = web_search("large language models", max_results=5)

    assert len(results) == 2
    assert results[0] == {
        "title": "LLM Basics",
        "url": "https://example.com/llm-basics",
        "snippet": "LLMs predict tokens.",
    }
    assert fake_client.last_call_kwargs["query"] == "large language models"
    assert fake_client.last_call_kwargs["max_results"] == 5


def test_web_search_respects_max_results_even_if_api_returns_more(monkeypatch):
    monkeypatch.setattr("tools.search.settings.tavily_api_key", "fake-key")
    fake_client = _FakeTavilyClient(
        response={"results": [{"title": f"R{i}", "url": f"https://x/{i}", "content": "c"} for i in range(10)]}
    )
    monkeypatch.setattr("tools.search._get_client", lambda: fake_client)

    results = web_search("topic", max_results=3)
    assert len(results) == 3


def test_web_search_falls_back_to_stub_on_exception(monkeypatch):
    monkeypatch.setattr("tools.search.settings.tavily_api_key", "fake-key")
    fake_client = _FakeTavilyClient(raise_exc=RuntimeError("network error"))
    monkeypatch.setattr("tools.search._get_client", lambda: fake_client)

    results = web_search("topic")
    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/stub-result"


def test_web_search_falls_back_to_stub_on_empty_results(monkeypatch):
    monkeypatch.setattr("tools.search.settings.tavily_api_key", "fake-key")
    fake_client = _FakeTavilyClient(response={"results": []})
    monkeypatch.setattr("tools.search._get_client", lambda: fake_client)

    results = web_search("obscure topic with no hits")
    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/stub-result"


def test_web_search_handles_missing_fields_gracefully(monkeypatch):
    monkeypatch.setattr("tools.search.settings.tavily_api_key", "fake-key")
    fake_client = _FakeTavilyClient(response={"results": [{"url": "https://example.com/x"}]})
    monkeypatch.setattr("tools.search._get_client", lambda: fake_client)

    results = web_search("topic")
    assert results[0]["title"] == "(untitled)"
    assert results[0]["snippet"] == ""
