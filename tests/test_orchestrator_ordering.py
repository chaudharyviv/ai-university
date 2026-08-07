from agents.orchestrator import sort_by_pipeline_order


def test_sort_by_pipeline_order_fixes_alphabetical_input():
    # This is the exact order list_registered_agents() returns (alphabetical),
    # which was the bug: curriculum ran before its dependencies existed.
    alphabetical = ["curriculum", "notebook", "persona", "research"]
    assert sort_by_pipeline_order(alphabetical) == ["persona", "research", "curriculum", "notebook"]


def test_sort_by_pipeline_order_fixes_arbitrary_click_order():
    # Simulates a user clicking multiselect options in a random order.
    clicked = ["notebook", "curriculum", "persona", "research"]
    assert sort_by_pipeline_order(clicked) == ["persona", "research", "curriculum", "notebook"]


def test_sort_by_pipeline_order_respects_partial_selection():
    assert sort_by_pipeline_order(["curriculum", "persona"]) == ["persona", "curriculum"]


def test_sort_by_pipeline_order_appends_unknown_agents_at_end():
    result = sort_by_pipeline_order(["quiz", "persona"])
    assert result == ["persona", "quiz"]


def test_run_pipeline_rejects_unknown_agent_name_up_front():
    # Previously a typo'd agent name (e.g. "noebook") would silently get
    # appended at the end by sort_by_pipeline_order and only fail once
    # the pipeline reached it, after every other agent had already run
    # (and been paid for). Now it's rejected immediately.
    import pytest

    import agents  # noqa: F401 - triggers agent registration
    from agents.orchestrator import Orchestrator

    orch = Orchestrator()
    with pytest.raises(ValueError, match="Unknown agent name"):
        orch.run_pipeline(agent_names=["persona", "noebook"], initial_context={"topic": "x"})
