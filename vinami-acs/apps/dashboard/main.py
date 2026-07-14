"""API-only Streamlit platform status dashboard with no clinical business logic."""

from __future__ import annotations

import streamlit as st

from apps.dashboard.api.client import get
from apps.dashboard.components.case_header.header import render as render_case_header
from apps.dashboard.components.common.status_card import render_status_card
from apps.dashboard.components.common.unavailable_state import render as render_unavailable
from apps.dashboard.components.patient_queue.queue import render as render_queue
from apps.dashboard.demo.adapter import active_cases
from apps.dashboard.demo.adapter import enabled as demo_enabled
from apps.dashboard.models.view_models import StatusView
from apps.dashboard.theme.styles import apply


def render_status(title: str, path: str) -> None:
    """Render an API status card without interpreting clinical data."""
    result = get(path)
    state = "healthy" if result.status_code and result.status_code < 300 else "error"
    render_status_card(StatusView(title, state, str(result.payload or result.error)))


def main() -> None:
    """Run the Streamlit entry point for platform availability only."""
    st.set_page_config(page_title="VinAMI ACS", layout="wide")
    apply()
    st.title("VinAMI ACS Command Center")
    st.caption("Research-use prototype. Demonstration rule - not for clinical use.")
    demo_mode = demo_enabled()
    if demo_mode:
        st.info("Synthetic demonstration data. It is isolated from the production API.")
    filters = st.columns(4)
    for column, label in zip(
        filters, ("Priority", "Workflow state", "Overdue", "Assigned team"), strict=True
    ):
        column.selectbox(label, ["All"], key=f"filter_{label}")
    health, readiness, alerts = st.columns(3)
    with health:
        render_status("API health", "/health")
    with readiness:
        render_status("Database readiness", "/ready")
    with alerts:
        render_status("Safety alerts API", "/api/v1/alerts")
    st.subheader("Active ACS Cases")
    cases = get("/api/v1/clinical-cases") if not demo_mode else None
    if demo_mode:
        render_queue(active_cases())
    elif cases is not None and cases.error:
        st.error(f"Case queue unavailable: {cases.error}")
    else:
        payload = cases.payload if cases is not None and cases.payload else {}
        raw_items = payload.get("items", [])
        items = (
            [item for item in raw_items if isinstance(item, dict)]
            if isinstance(raw_items, list)
            else []
        )
        render_queue(items)
    render_case_header()
    tabs = st.tabs(["Triage", "ECG", "Troponin", "Pathway", "Tasks & Alerts", "Timeline"])
    for tab, title in zip(
        tabs,
        (
            "Structured symptoms and vitals",
            "AI-supported finding and model score",
            "Serial troponin and delta",
            "Demonstration pathway",
            "Pending physician review",
            "Complete case timeline",
        ),
        strict=True,
    ):
        with tab:
            st.subheader(title)
            render_unavailable("GET /api/v1/clinical-cases/{case_id}")


if __name__ == "__main__":
    main()
