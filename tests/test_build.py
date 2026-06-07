from app.graph import build
from app.graph.state import Critique


def _initial(max_iterations=2):
    return {
        "session_id": "s1",
        "question": "Q",
        "plan": [],
        "evidence": [],
        "draft_findings": "",
        "critique": None,
        "iteration": 0,
        "max_iterations": max_iterations,
        "report_md": "",
        "citations_valid": False,
        "low_confidence": False,
        "stripped_fraction": 0.0,
    }


def _stub_common(monkeypatch):
    """Stub every node except the critic (the test sets that) — no LLM/DB needed."""
    monkeypatch.setattr(build, "planner_node", lambda s: {"plan": ["q1"]})
    monkeypatch.setattr(
        build, "researcher_node", lambda s: {"evidence": [], "draft_findings": "d"}
    )
    monkeypatch.setattr(build, "writer_node", lambda s: {"report_md": "report"})
    monkeypatch.setattr(
        build,
        "citation_validator_node",
        lambda s: {
            "citations_valid": True,
            "low_confidence": False,
            "stripped_fraction": 0.0,
        },
    )


def test_critic_loop_runs_up_to_max_iterations_then_writes(monkeypatch):
    _stub_common(monkeypatch)
    # critic always wants more research → the cap is what must stop the loop
    monkeypatch.setattr(
        build,
        "critic_node",
        lambda s: {
            "critique": Critique(groundedness=0.1, needs_more_research=True, gaps=["g"])
        },
    )
    writer_seen_iteration = []
    monkeypatch.setattr(
        build,
        "writer_node",
        lambda s: (
            writer_seen_iteration.append(s["iteration"]) or {"report_md": "report"}
        ),
    )

    graph = build.build_graph()
    out = graph.invoke(_initial(max_iterations=2))

    assert out["iteration"] == 2  # Researcher ran exactly max_iterations times
    assert writer_seen_iteration == [2]  # Writer ran once, only after the cap
    assert out["citations_valid"] is True  # reached the end (terminated)


def test_no_loop_back_when_critic_satisfied(monkeypatch):
    _stub_common(monkeypatch)
    monkeypatch.setattr(
        build,
        "critic_node",
        lambda s: {
            "critique": Critique(groundedness=0.95, needs_more_research=False, gaps=[])
        },
    )

    graph = build.build_graph()
    out = graph.invoke(_initial(max_iterations=2))

    assert (
        out["iteration"] == 1
    )  # one research pass, critic satisfied → straight to Writer
    assert out["report_md"] == "report"
