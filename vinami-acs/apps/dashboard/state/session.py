"""Typed, deterministic dashboard session-state boundary."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True, slots=True)
class DashboardState:
    """Presentation navigation state only; it contains no clinical decision logic."""

    selected_case_id: str | None
    demo_mode: bool


def get_state() -> DashboardState:
    """Read initialized state through the only allowed Streamlit session access module."""
    if "dashboard_selected_case_id" not in st.session_state:
        st.session_state.dashboard_selected_case_id = None
    return DashboardState(
        selected_case_id=st.session_state.dashboard_selected_case_id,
        demo_mode=st.session_state.get("dashboard_demo_mode", False),
    )


def select_case(case_id: str | None) -> None:
    """Update selected case without mutating filters or any clinical fact."""
    st.session_state.dashboard_selected_case_id = case_id
