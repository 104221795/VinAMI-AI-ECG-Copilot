"""Controlled unavailable state for missing API contracts."""

from __future__ import annotations

import streamlit as st


def render(contract: str) -> None:
    """Explain a missing contract without fabricating a production response."""
    st.warning(f"Unavailable: the API contract `{contract}` has not been delivered yet.")
    st.caption("No clinical data is inferred or fabricated in production mode.")
