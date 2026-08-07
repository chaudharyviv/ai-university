from __future__ import annotations

import streamlit as st

from config import settings

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
st.title("⚙️ Settings")

st.caption("Read-only view of current config. Secrets are never displayed - only whether they're set.")

st.json(
    {
        "app_env": settings.app_env.value,
        "log_level": settings.log_level.value,
        "primary_model": settings.primary_model,
        "fallback_model": settings.fallback_model,
        "max_tokens": settings.max_tokens,
        "anthropic_key_configured": settings.has_anthropic,
        "openai_key_configured": settings.has_openai,
        "workspace_dir": str(settings.workspace_dir),
        "outputs_dir": str(settings.outputs_dir),
        "database_configured": bool(settings.database_url),
        "max_cost_per_run_usd": settings.max_cost_per_run_usd,
    }
)

st.info("To change these, edit your `.env` file and restart the app.")
