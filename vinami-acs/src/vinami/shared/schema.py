"""Single source of truth for runtime schema readiness."""

EXPECTED_ALEMBIC_HEAD = "a7d3f0b2c6e1"

CRITICAL_TABLES = frozenset(
    {
        "alembic_version",
        "patients",
        "encounters",
        "clinical_cases",
        "clinical_workflows",
        "physician_decisions",
        "outbox_events",
        "audit_logs",
        "timeline_events",
    }
)
