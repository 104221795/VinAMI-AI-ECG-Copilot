"""Single source of truth for runtime schema readiness."""

EXPECTED_ALEMBIC_HEAD = "f19c7a42d8e1"

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
        "command_idempotency",
    }
)
