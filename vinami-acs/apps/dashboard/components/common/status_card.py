"""Side-effect-free status card presentation."""

import streamlit as st
from apps.dashboard.models.view_models import StatusView


def render_status_card(view: StatusView) -> None:
    st.markdown(f"### {view.title}")
    if view.state == "healthy":
        st.success(view.detail)
    elif view.state == "error":
        st.error(view.detail)
    else:
        st.warning(view.detail)
    if view.stale:
        st.caption("Stale data - refresh before acting.")
