from __future__ import annotations

import streamlit as st

import agents  # noqa: F401 - triggers agent registration
from agents.base import list_registered_agents
from agents.orchestrator import REVIEWABLE_AGENTS, Orchestrator, sort_by_pipeline_order
from config import settings
from models.persona_archetypes import PERSONA_ARCHETYPE_OPTIONS
from tools.export import export_run

st.set_page_config(page_title="Run Course", page_icon="▶️", layout="wide")
st.title("▶️ Run Course")

# "reviewer" isn't a standalone pipeline step - the Orchestrator invokes it
# automatically against reviewable agents' output (see enable_review below).
# Selecting it directly from this list would just fail, so it's excluded here.
registered = [a for a in list_registered_agents() if a != "reviewer"]

if not registered:
    st.warning(
        "No agents are registered yet, so there's nothing to run."
    )
    st.stop()

# Display in dependency order (persona -> research -> curriculum -> notebook),
# not the registry's alphabetical order, so the UI doesn't invite you to
# pick agents in a broken order.
display_order = sort_by_pipeline_order(registered)

topic = st.text_input("Course topic", placeholder="e.g. Introduction to Machine Learning")
persona_archetype = st.selectbox(
    "Target audience",
    options=PERSONA_ARCHETYPE_OPTIONS,
    help="Fixed archetypes hardcode audience level and tone for reproducible runs - only "
    "prerequisites/learning goals are still generated per-topic. 'Custom' lets the Persona "
    "agent infer everything from the topic, as before (results may vary run to run).",
)
selected_agents = st.multiselect(
    "Agents to run",
    options=display_order,
    default=display_order,
    help="They'll always execute in dependency order (persona → research → curriculum → "
    "notebook) regardless of the order you select them in.",
)
enable_review = st.checkbox(
    "Enable reviewer loop",
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
            initial_context={"topic": topic, "persona_archetype": persona_archetype},
            enable_review=enable_review,
        )
    # Stored in session_state (not a local var) so the export section below
    # survives the rerun that happens when its own button is clicked.
    st.session_state["last_run"] = run
    st.session_state.pop("export_zip", None)  # stale export from a prior run

last_run = st.session_state.get("last_run")

if last_run is not None:
    if last_run.success:
        st.success(f"Run {last_run.run_id} completed. Total cost: ${last_run.total_cost_usd:.4f}")
    else:
        st.error(f"Run {last_run.run_id} stopped early: {last_run.stop_reason}")

    for result in last_run.results:
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

    st.divider()
    st.subheader("📦 Export (Phase 5)")

    if "curriculum" not in last_run.context:
        st.info("Run the curriculum agent (and ideally notebook/code/diagram/quiz/assignment) to enable export.")
    else:
        if st.button("Generate course.ipynb + slides.pptx"):
            with st.spinner("Building notebook and slide deck..."):
                try:
                    zip_path = export_run(last_run.run_id, last_run.context)
                    st.session_state["export_zip"] = zip_path
                except Exception as exc:  # noqa: BLE001 - surface any export failure in the UI
                    st.error(f"Export failed: {exc}")

        export_zip = st.session_state.get("export_zip")
        if export_zip and export_zip.exists():
            with open(export_zip, "rb") as f:
                st.download_button(
                    "⬇️ Download course materials (.zip)",
                    f,
                    file_name=export_zip.name,
                    mime="application/zip",
                )
            st.caption("Contains course.ipynb and course_slides.pptx")