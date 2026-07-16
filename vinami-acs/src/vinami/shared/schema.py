"""Single source of truth for runtime schema readiness."""

EXPECTED_ALEMBIC_HEAD = "b4e2d9c7a103"

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
        "outcomes",
        "clinical_research_exports",
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
        "troponin_assay_definitions",
        "troponin_evidence_results",
        "laboratory_import_jobs",
        "clinician_troponin_reviews",
        "repeat_troponin_requests",
    }
)
