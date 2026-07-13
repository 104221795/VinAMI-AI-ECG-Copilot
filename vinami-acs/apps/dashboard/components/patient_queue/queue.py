"""Presentation-only patient queue with explicit empty and stale states."""

from collections.abc import Sequence

import streamlit as st


def render(items: Sequence[dict[str, object]]) -> None:
    if not items:
        st.info("No active ACS cases returned by the API.")
        return
    st.dataframe(items, use_container_width=True, hide_index=True)
