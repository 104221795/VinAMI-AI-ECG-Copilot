# Streamlit Migration

The Next.js application is intended to become the default product frontend only after every F0 gate, including clean Docker Compose startup, passes.

The existing Streamlit dashboard must then move to `legacy/streamlit-dashboard`, remain available only through an explicit Compose legacy profile and stay documented for historical comparison. It must not start with the default stack.

Current status is recorded in `f0-completion-report.md`. Streamlit is not deleted. No backend behavior may be changed by the migration.
