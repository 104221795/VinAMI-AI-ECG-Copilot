"""Single source of truth for runtime schema readiness."""

EXPECTED_ALEMBIC_HEAD = "b7f3a9d1e6c2"

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
        "triage_assessments",
        "vital_observation_sets",
        "vital_measurements",
        "ecg_artifacts",
        "ecg_study_details",
        "ecg_ingestion_jobs",
        "ecg_ai_analyses",
        "physician_ecg_interpretations",
        "dynamic_ecg_comparisons",
        "ecg_repeat_reminders",
    }
)
