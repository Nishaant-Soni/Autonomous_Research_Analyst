"""Researcher node (PRD §6, FR-3/FR-4).

A tool-using loop: the LLM decides what to search for, calling `web_search` and
`rag_retrieve`; our code executes the real retrievers and feeds the results back. The model
then writes prose `draft_findings`.

Source integrity: the canonical `Evidence` objects are the ones our retrievers return (real
`source_url` / `source_chunk_id`) — the model never fabricates them. It only picks queries and
writes the narrative. `evidence` is the canonical artifact (per 2.3); `draft_findings` is an
advisory hint the Writer (2.5) need not treat as source-of-truth. We return only the *new*
evidence gathered this pass — the graph's additive reducer (2.1) accumulates across loop-backs.

On a critic loop-back, the prompt narrows scope to the gaps the Critic named (PRD §6).
"""

import json
from typing import Any

from app.agents.untrusted import GUARD, wrap_untrusted
from app.graph.state import Critique, ResearchState
from app.llm.provider import LLMProvider, get_default_provider
from app.models.evidence import Evidence
from app.retrieval.rag import rag_retrieve
from app.retrieval.web import web_search

_MAX_OUTPUT_TOKENS = (
    6000  # per-agent token budget (PRD §12), applied per call in the loop
)

_SYSTEM_PROMPT = (
    "You are the research agent of an autonomous research system. Gather evidence using the "
    "provided tools and synthesize concise draft findings.\n"
    "- Use web_search for current/public information and rag_retrieve for the private document "
    "corpus. Call them as often as needed, with focused queries.\n"
    "- Ground every statement in retrieved evidence; do not rely on prior knowledge.\n"
    f"- {GUARD}"
)

_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "web_search",
        "description": "Search the live web. Returns extracted content snippets, each with a source URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "A focused search query."}
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "rag_retrieve",
        "description": "Retrieve relevant passages from the private ingested document corpus via vector similarity.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "A focused retrieval query."}
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
]


def _dispatch(
    name: str,
    query: str,
    user_id: int | None = None,
    allow_all_users: bool = False,
) -> list[Evidence]:
    # Looked up by name (not a module-level dict) so tests can monkeypatch the retrievers.
    if name == "web_search":
        return web_search(query)
    if name == "rag_retrieve":
        return rag_retrieve(query, user_id=user_id, allow_all_users=allow_all_users)
    return []


def _format_results(results: list[Evidence]) -> str:
    # Each snippet is untrusted (web/corpus) — fence it so the model treats it as data, not
    # instructions (see app/agents/untrusted.py). The source attribution stays inside the fence.
    if not results:
        return "No results found."
    return "\n".join(
        wrap_untrusted(
            f"{ev.content} (source: {ev.source_url or f'chunk #{ev.source_chunk_id}'})"
        )
        for ev in results
    )


def _build_initial_input(
    question: str, plan: list[str], critique: Critique | None
) -> list[dict[str, Any]]:
    if critique is not None and critique.needs_more_research:
        gaps = (
            "\n".join(f"- {g}" for g in critique.gaps)
            or "- (strengthen weakly-supported areas)"
        )
        task = f"A previous research pass was incomplete. Focus ONLY on filling these gaps:\n{gaps}"
    else:
        subqs = "\n".join(f"- {q}" for q in plan)
        task = f"Investigate each of these sub-questions:\n{subqs}"
    user = (
        f"Research question: {question}\n\n{task}\n\n"
        "Use the web_search and rag_retrieve tools to gather evidence, then write concise, "
        "well-organized findings grounded only in what you retrieved."
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _query_of(call: Any) -> str:
    try:
        return json.loads(call.arguments).get("query", "")
    except (json.JSONDecodeError, TypeError, AttributeError):
        return ""


def run_researcher(
    question: str,
    plan: list[str],
    critique: Critique | None = None,
    provider: LLMProvider | None = None,
    max_rounds: int = 6,
    user_id: int | None = None,
    allow_all_users: bool = False,
) -> dict:
    """Run the tool-using loop. Returns `{"evidence": <new>, "draft_findings": <prose>}`."""
    provider = provider or get_default_provider()
    conversation = _build_initial_input(question, plan, critique)
    gathered: list[Evidence] = []

    for _ in range(max_rounds):
        response = provider.complete(
            conversation, tools=_TOOLS, max_output_tokens=_MAX_OUTPUT_TOKENS
        )
        conversation = conversation + list(response.output)  # carry model items forward
        calls = [
            it for it in response.output if getattr(it, "type", None) == "function_call"
        ]
        if not calls:
            return {"evidence": gathered, "draft_findings": response.output_text}
        for call in calls:
            results = _dispatch(
                call.name,
                _query_of(call),
                user_id=user_id,
                allow_all_users=allow_all_users,
            )
            gathered.extend(results)
            conversation.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": _format_results(results),
                }
            )

    # Round cap hit: force a final synthesis with no tools so the loop always terminates.
    conversation.append(
        {
            "role": "user",
            "content": "Stop searching and write your findings now from the evidence above.",
        }
    )
    final = provider.complete(
        conversation, tools=None, max_output_tokens=_MAX_OUTPUT_TOKENS
    )
    return {"evidence": gathered, "draft_findings": final.output_text}


def researcher_node(state: ResearchState) -> dict:
    """Graph node: gather evidence + draft findings for the question/plan (and any critique)."""
    return run_researcher(
        state["question"],
        state["plan"],
        state.get("critique"),
        user_id=state.get("user_id"),
        allow_all_users=state.get("allow_all_users", False),
    )
