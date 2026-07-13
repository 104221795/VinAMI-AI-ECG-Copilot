"""Explicit deterministic development demo adapter, isolated from production API reads."""

from __future__ import annotations

import os


def enabled() -> bool:
    """Return whether the operator explicitly enabled synthetic demonstration data."""
    return os.getenv("VINAMI_DASHBOARD_DEMO_MODE", "false").lower() == "true"


def active_cases() -> list[dict[str, object]]:
    """Return one deterministic, clearly synthetic queue item for UI-only demonstration."""
    return [
        {
            "reference": "SYNTH-ACS-001",
            "priority": "urgent",
            "workflow_state": "PHYSICIAN_REVIEW_REQUIRED",
            "ecg_status": "AI-supported finding available",
            "troponin_status": "serial result pending",
            "alert": "Review",
        }
    ]
