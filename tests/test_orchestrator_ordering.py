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
