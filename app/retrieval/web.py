"""Tavily web search — the `web_search` tool (FR-3).

Returns clean, extractable content + source URL per result, mapped to the shared
`Evidence` shape. Tavily is built for agents (search + extraction in one call), so no
separate scraping step is needed.
"""

from app.config import settings
from app.models.evidence import Evidence


def _get_client():
    from tavily import TavilyClient

    return TavilyClient(api_key=settings.tavily_api_key)


def web_search(query: str, max_results: int = 5) -> list[Evidence]:
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY is not set")

    response = _get_client().search(query=query, max_results=max_results)

    evidence: list[Evidence] = []
    for result in response.get("results", []):
        url = result.get("url")
        if not url:  # a result with no source URL can't be cited — skip it
            continue
        evidence.append(
            Evidence(
                content=result.get("content") or "",
                source_url=url,
                retriever="web",
            )
        )
    return evidence
