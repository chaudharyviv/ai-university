from __future__ import annotations

import streamlit as st

import agents  # noqa: F401 - triggers agent registration
from agents.base import list_registered_agents
from agents.orchestrator import REVIEWABLE_AGENTS, Orchestrator, sort_by_pipeline_order
from config import settings

st.set_page_config(page_title="Run Course", page_icon="▶️", layout="wide")
st.title("▶️ Run Course")

# "reviewer" isn't a standalone pipeline step - the Orchestrator invokes it
# automatically against reviewable agents' output (see enable_review below).
# Selecting it directly from this list would just fail, so it's excluded here.
registered = [a for a in list_registered_agents() if a != "reviewer"]

if not registered:
    st.warning(
        "No agents are registered yet, so there's nothing to run. "
        "This page will come alive in Phase 2 once Persona/Research/"
        "Curriculum/Notebook agents exist."
    )
    st.stop()

# Display in dependency order (persona -> research -> curriculum -> notebook),
# not the registry's alphabetical order, so the UI doesn't invite you to
# pick agents in a broken order.
display_order = sort_by_pipeline_order(registered)

topic = st.text_input("Course topic", placeholder="e.g. Introduction to Bayesian Statistics")
selected_agents = st.multiselect(
    "Agents to run",
    options=display_order,
    default=display_order,
    help="They'll always execute in dependency order (persona → research → curriculum → "
    "notebook) regardless of the order you select them in.",
)
enable_review = st.checkbox(
    "Enable reviewer loop (Phase 4)",
    value=settings.enable_review,
    help=f"Notebook/Code/Diagram/Quiz/Assignment/Speaker Notes get reviewed and, if rejected, "
    f"re-generated with feedback (up to {settings.review_max_attempts} attempts). Adds extra "
    f"LLM calls and cost per reviewable agent - uncheck to skip it.",
)

if st.button("Run pipeline", type="primary", disabled=not (topic and selected_agents)):
    with st.spinner("Running pipeline..."):
        orchestrator = Orchestrator()
        run = orchestrator.run_pipeline(
            agent_names=selected_agents,
            initial_context={"topic": topic},
            enable_review=enable_review,
        )

    if run.success:
        st.success(f"Run {run.run_id} completed. Total cost: ${run.total_cost_usd:.4f}")
    else:
        st.error(f"Run {run.run_id} stopped early: {run.stop_reason}")

    for result in run.results:
        with st.expander(f"{result.agent_name} — {'✅' if result.success else '❌'}"):
            st.write(f"Model: `{result.model_used}`")
            st.write(f"Latency: {result.latency_seconds:.2f}s")
            st.write(f"Tokens: {result.input_tokens} in / {result.output_tokens} out")
            st.write(f"Cost: ${result.estimated_cost_usd:.4f}")

            review_history = result.metadata.get("review_history") if result.metadata else None
            if result.agent_name in REVIEWABLE_AGENTS and review_history:
                st.write(f"Reviewer attempts: {result.metadata.get('review_attempts', 0)}")
                for i, verdict in enumerate(review_history, start=1):
                    icon = "✅" if verdict["approved"] else "🔁"
                    st.write(f"{icon} Review {i}: {verdict['feedback']}")
                    if verdict["issues"]:
                        st.write("Issues: " + "; ".join(verdict["issues"]))

            if result.error:
                st.error(result.error)
            else:
                st.write(result.output)
