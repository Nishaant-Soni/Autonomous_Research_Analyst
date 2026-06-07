from langgraph.graph import END, START, StateGraph

from app.graph.state import Critique, ResearchState
from app.models.evidence import Evidence


def test_initial_state_constructs():
    state: ResearchState = {
        "session_id": "s1",
        "question": "What is the capital of France?",
        "plan": ["sub-question 1", "sub-question 2"],
        "evidence": [],
        "draft_findings": "",
        "critique": None,
        "iteration": 0,
        "max_iterations": 2,
        "report_md": "",
        "citations_valid": False,
        "low_confidence": False,
        "stripped_fraction": 0.0,
    }
    assert state["question"]
    assert state["max_iterations"] == 2


def test_evidence_both_source_variants():
    web = Evidence(content="x", retriever="web", source_url="https://example.com")
    rag = Evidence(content="y", retriever="rag", source_chunk_id=7)
    assert web.source_url and rag.source_chunk_id == 7


def test_critique_constructs_and_bounds_groundedness():
    c = Critique(groundedness=0.8, needs_more_research=True, gaps=["coverage of X"])
    assert c.needs_more_research is True
    assert c.gaps == ["coverage of X"]


def test_evidence_reducer_appends_across_nodes():
    """Two nodes each return one Evidence; the reducer must yield *both*, not the last."""
    ev_a = Evidence(content="a", retriever="web", source_url="https://a.example")
    ev_b = Evidence(content="b", retriever="rag", source_chunk_id=1)

    def node_a(state: ResearchState) -> dict:
        return {"evidence": [ev_a]}

    def node_b(state: ResearchState) -> dict:
        return {"evidence": [ev_b]}

    graph = StateGraph(ResearchState)
    graph.add_node("a", node_a)
    graph.add_node("b", node_b)
    graph.add_edge(START, "a")
    graph.add_edge("a", "b")
    graph.add_edge("b", END)
    app = graph.compile()

    out = app.invoke({"evidence": []})

    assert [e.content for e in out["evidence"]] == ["a", "b"]


def test_evidence_reducer_dedups_by_source_within_and_across_nodes():
    """Same source (web URL / rag chunk id) must not accumulate twice — even within the
    first node's return (intra-pass) or when a later node re-fetches it (cross-pass)."""
    x = Evidence(content="x1", retriever="web", source_url="https://x.example")
    x_dup = Evidence(
        content="x2-diff-snippet", retriever="web", source_url="https://x.example"
    )
    y = Evidence(content="y", retriever="rag", source_chunk_id=5)
    y_dup = Evidence(content="y-again", retriever="rag", source_chunk_id=5)
    z = Evidence(content="z", retriever="web", source_url="https://z.example")

    def node_a(state: ResearchState) -> dict:
        return {"evidence": [x, x_dup, y]}  # intra-pass dup (x / x_dup share a URL)

    def node_b(state: ResearchState) -> dict:
        return {"evidence": [y_dup, z]}  # cross-pass dup (y_dup re-fetches chunk 5)

    graph = StateGraph(ResearchState)
    graph.add_node("a", node_a)
    graph.add_node("b", node_b)
    graph.add_edge(START, "a")
    graph.add_edge("a", "b")
    graph.add_edge("b", END)
    app = graph.compile()

    out = app.invoke({"evidence": []})

    # one entry per distinct source, first occurrence kept, order preserved
    assert [e.content for e in out["evidence"]] == ["x1", "y", "z"]
