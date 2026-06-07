import os

import pytest

from app import config
from app.retrieval import web


class _FakeClient:
    def search(self, query, max_results=5):
        return {
            "results": [
                {
                    "title": "France",
                    "url": "https://en.wikipedia.org/wiki/France",
                    "content": "Paris is the capital of France.",
                },
                {"title": "no url", "content": "should be skipped"},  # no url
            ]
        }


def test_web_search_maps_results_to_evidence(monkeypatch):
    monkeypatch.setattr(web, "_get_client", lambda: _FakeClient())
    monkeypatch.setattr(config.settings, "tavily_api_key", "test-key")

    results = web.web_search("capital of France")

    assert len(results) == 1  # the url-less result is dropped
    ev = results[0]
    assert ev.retriever == "web"
    assert ev.source_url == "https://en.wikipedia.org/wiki/France"
    assert ev.content


def test_web_search_requires_key(monkeypatch):
    monkeypatch.setattr(config.settings, "tavily_api_key", "")
    with pytest.raises(RuntimeError):
        web.web_search("anything")


@pytest.mark.skipif(
    os.environ.get("RUN_WEB_TESTS") != "1",
    reason="set RUN_WEB_TESTS=1 with a real TAVILY_API_KEY (live network call)",
)
def test_web_search_live():
    results = web.web_search("What is the capital of France?", max_results=3)

    assert results
    top = results[0]
    assert top.retriever == "web"
    assert top.source_url.startswith("http")
    assert top.content
