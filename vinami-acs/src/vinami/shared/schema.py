"""Single source of truth for runtime schema readiness."""

EXPECTED_ALEMBIC_HEAD = "d4c8a91e7b32"

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
