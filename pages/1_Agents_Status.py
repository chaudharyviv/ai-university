from __future__ import annotations

import streamlit as st

import agents  # noqa: F401 - triggers agent registration
from agents.base import list_registered_agents

st.set_page_config(page_title="Agents Status", page_icon="🤖", layout="wide")
st.title("🤖 Agents Status")

registered = list_registered_agents()

if not registered:
    st.info(
        "No agents registered yet. This is expected in Phase 1 - specialized "
        "agents (Persona, Research, Curriculum, Notebook, ...) are added in "
        "Phase 2 via the `@register_agent(...)` decorator in `agents/base.py`."
    )
else:
    st.write(f"**{len(registered)} agent(s) registered:**")
    for name in registered:
        st.markdown(f"- `{name}`")
