from __future__ import annotations

import streamlit as st

from config import settings

st.set_page_config(page_title="File Browser", page_icon="📁", layout="wide")
st.title("📁 File Browser")

workspace = settings.workspace_dir
run_dirs = sorted([p for p in workspace.iterdir() if p.is_dir()], reverse=True) if workspace.exists() else []

if not run_dirs:
    st.info("No runs yet. Files will appear here after you run a course from the **Run Course** page.")
else:
    selected = st.selectbox("Run ID", options=[p.name for p in run_dirs])
    run_dir = workspace / selected
    files = sorted(p for p in run_dir.rglob("*") if p.is_file())

    if not files:
        st.write("No files in this run yet.")
    for f in files:
        rel = f.relative_to(run_dir)
        with st.expander(str(rel)):
            try:
                st.code(f.read_text(encoding="utf-8")[:5000])
            except UnicodeDecodeError:
                st.write(f"Binary file, {f.stat().st_size} bytes")
