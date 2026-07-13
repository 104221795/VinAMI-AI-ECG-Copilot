# UI Architecture

The Streamlit dashboard is an API client only. `apps/dashboard/api/` owns HTTP access; feature entry points coordinate reads; presentation components receive view models or display-safe values; `state/session.py` is the only module permitted to access `st.session_state`.

When an API contract is absent, presentation shows `unavailable_state` with the exact missing versioned endpoint. Development demo data is available only when `VINAMI_DASHBOARD_DEMO_MODE=true` and never posts to the API.
