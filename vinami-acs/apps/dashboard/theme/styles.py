"""Accessible dark design tokens injected by the dashboard shell."""

import streamlit as st


def apply() -> None:
    st.markdown(
        "<style>.stApp{background:#0b1220;color:#e5edf7}"
        ".metric-card{border:1px solid #334155;padding:14px;border-radius:8px;"
        "background:#111c2e}</style>",
        unsafe_allow_html=True,
    )
