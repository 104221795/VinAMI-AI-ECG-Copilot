"""R13/R14/R21 clinical workflow automation read policies.

The functions in this module produce backend-owned operational suggestions and
digests. They do not create clinical conclusions, workflow transitions, or
tasks; every suggested task still requires human confirmation through the
existing workflow APIs.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence
from uuid import UUID

AUTOMATION_POLICY_VERSION = "vinami-r13-r14-r21-demo-v1"
SAFETY_NOTICE = (
    "Demonstration automation - not for clinical use. Missing or unknown evidence is "
    "incomplete data, not negative evidence. Suggested work requires human confirmation."
)

_INACTIVE_TASK_STATUSES = {"completed", "cancelled"}
_UNCERTAIN_STATES = {"unknown", "not_assessed", "missing", ""}
_REQUIRED_ORDER = ("triage", "symptom_onset", "risk_factors", "vitals", "ecg", "troponin")


def build_case_automation(
    *,
    case_id: UUID,
    now: datetime,
    triage: Mapping[str, object] | None,
    vitals: Mapping[str, object] | None,
    ecg: Mapping[str, object] | None,
    troponin: Mapping[str, object] | None,
    evidence_freshness: Mapping[str, str] | None,
    missing_evidence: Sequence[str],
    stale_evidence: Sequence[str],
    technical_limits: Sequence[str],
    tasks: Sequence[Mapping[str, object]],
    alerts: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build the canonical backend automation bundle for one case projection."""
    items = _evidence_items(
        triage=triage,
        vitals=vitals,
        ecg=ecg,
        troponin=troponin or {},
        evidence_freshness=evidence_freshness or {},
        missing_evidence=missing_evidence,
        stale_evidence=stale_evidence,
        technical_limits=technical_limits,
    )
    return {
        "policy_version": AUTOMATION_POLICY_VERSION,
        "safety_notice": SAFETY_NOTICE,
        "completeness": _completeness(items),
        "suggested_tasks": _suggested_tasks(case_id, now, items, tasks, alerts),
        "alert_digest": summarize_alert_digest(alerts),
    }


def summarize_alert_digest(alerts: Sequence[Mapping[str, object]]) -> tuple[dict[str, object], ...]:
    """Group unresolved alerts for display without suppressing any source alert."""
    groups: dict[tuple[str, str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for alert in alerts:
        key = (
            _text(alert.get("alert_type"), "unknown_alert"),
            _text(alert.get("source"), "unknown_source"),
            _text(alert.get("severity"), "review"),
            _text(alert.get("status"), "active"),
        )
        groups[key].append(alert)

    digest: list[dict[str, object]] = []
    for (alert_type, source, severity, status), grouped in groups.items():
        latest = max(grouped, key=lambda item: _datetime_sort_key(item.get("raised_at")))
        digest.append(
            {
                "group_key": hashlib.sha256(
                    f"{alert_type}|{source}|{severity}|{status}".encode()
                ).hexdigest()[:16],
                "alert_type": alert_type,
                "source": source,
                "severity": severity,
                "status": status,
                "count": len(grouped),
                "representative_alert_id": _optional_text(latest.get("alert_id")),
                "alert_ids": tuple(_text(item.get("alert_id")) for item in grouped),
                "latest_raised_at": latest.get("raised_at"),
                "max_escalation_level": max(_int(item.get("escalation_level")) for item in grouped),
                "message": _text(latest.get("message"), "Operational alert requires review."),
                "critical_preserved": severity in {"urgent", "critical"},
            }
        )
    return tuple(
        sorted(
            digest,
            key=lambda item: (
                _severity_rank(_text(item["severity"])),
                _datetime_sort_key(item["latest_raised_at"]),
                _text(item["alert_type"]),
            ),
            reverse=True,
        )
    )


def _evidence_items(
    *,
    triage: Mapping[str, object] | None,
    vitals: Mapping[str, object] | None,
    ecg: Mapping[str, object] | None,
    troponin: Mapping[str, object],
    evidence_freshness: Mapping[str, str],
    missing_evidence: Sequence[str],
    stale_evidence: Sequence[str],
    technical_limits: Sequence[str],
) -> tuple[dict[str, object], ...]:
    missing = {_canonical_name(item) for item in missing_evidence}
    stale = {_canonical_name(item) for item in stale_evidence}
    technical = tuple(str(item) for item in technical_limits)

    item_status: dict[str, tuple[str, str]] = {}
    item_status["triage"] = _status_from_presence(
        triage is not None and bool(_text(triage.get("chief_complaint"), "")),
        "Triage documentation is not current.",
    )
    item_status["vitals"] = _status_from_presence(
        vitals is not None and bool(vitals.get("measurements")),
        "No current vital-sign observation set is available.",
    )
    item_status["ecg"] = _status_from_presence(
        ecg is not None,
        "No current ECG evidence is available.",
    )
    item_status["troponin"] = _status_from_presence(
        _int(troponin.get("result_count")) > 0,
        "No effective troponin result is available.",
    )
    item_status["symptom_onset"] = _symptom_onset_status(triage)
    item_status["risk_factors"] = _risk_factor_status(triage)

    result: list[dict[str, object]] = []
    for name in _REQUIRED_ORDER:
        status, reason = item_status[name]
        freshness_state = evidence_freshness.get(name)
        if name in missing:
            status, reason = "missing", _default_missing_reason(name)
        if freshness_state == "stale" or name in stale:
            status, reason = "stale", f"{_label(name)} is older than the current demo freshness policy."
        if name == "ecg" and _ecg_has_technical_limit(ecg, technical):
            status, reason = "technical_limit", "Latest ECG has technical limitations."
        result.append(
            {
                "evidence_type": name,
                "status": status,
                "reason": reason,
                "not_negative_evidence": status in {"missing", "stale", "technical_limit"},
            }
        )
    return tuple(result)


def _completeness(items: Sequence[Mapping[str, object]]) -> dict[str, object]:
    current_count = sum(1 for item in items if item["status"] == "current")
    total = len(items)
    score = round((current_count / total) * 100) if total else 0
    missing = tuple(_text(item["evidence_type"]) for item in items if item["status"] == "missing")
    stale = tuple(_text(item["evidence_type"]) for item in items if item["status"] == "stale")
    technical = tuple(
        _text(item["evidence_type"]) for item in items if item["status"] == "technical_limit"
    )
    if technical:
        status = "technically_limited"
    elif missing:
        status = "incomplete"
    elif stale:
        status = "stale"
    else:
        status = "complete"
    return {
        "score": score,
        "status": status,
        "required_count": total,
        "current_count": current_count,
        "items": tuple(items),
        "missing_evidence": missing,
        "stale_evidence": stale,
        "technical_limits": technical,
        "not_negative_evidence_notice": (
            "Missing, unknown, stale, or technically limited evidence is not negative evidence."
        ),
    }


def _suggested_tasks(
    case_id: UUID,
    now: datetime,
    items: Sequence[Mapping[str, object]],
    tasks: Sequence[Mapping[str, object]],
    alerts: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    active_task_types = {
        _text(task.get("task_type"))
        for task in tasks
        if _text(task.get("status")) not in _INACTIVE_TASK_STATUSES
    }
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for item in items:
        if item["status"] == "current":
            continue
        task_type = _task_type_for_gap(_text(item["evidence_type"]))
        if task_type in active_task_types:
            continue
        grouped[task_type].append(item)

    if any(_text(alert.get("severity")) in {"urgent", "critical"} for alert in alerts):
        if "physician_review" not in active_task_types:
            grouped["physician_review"].append(
                {
                    "evidence_type": "unresolved_alert",
                    "status": "review_required",
                    "reason": "Unresolved urgent alert requires physician review.",
                }
            )

    suggestions: list[dict[str, object]] = []
    for task_type, gaps in grouped.items():
        due_state = _due_state_for(task_type, gaps)
        due_at = _due_at_for(now, due_state)
        evidence_gaps = tuple(_text(gap["evidence_type"]) for gap in gaps)
        reason = "; ".join(_text(gap["reason"]) for gap in gaps)
        deduplication_key = (
            f"{AUTOMATION_POLICY_VERSION}:{case_id}:{task_type}:{','.join(evidence_gaps)}"
        )
        suggestions.append(
            {
                "suggestion_id": hashlib.sha256(deduplication_key.encode()).hexdigest()[:24],
                "task_type": task_type,
                "priority": "urgent"
                if due_state in {"due_now", "overdue"}
                else "priority",
                "due_state": due_state,
                "due_at": due_at,
                "reason": reason,
                "evidence_gaps": evidence_gaps,
                "deduplication_key": deduplication_key,
                "requires_confirmation": True,
                "can_create_directly": False,
                "policy_version": AUTOMATION_POLICY_VERSION,
                "safety_notice": SAFETY_NOTICE,
            }
        )
    return tuple(sorted(suggestions, key=lambda item: (_due_rank(_text(item["due_state"])), _text(item["task_type"]))))


def _symptom_onset_status(triage: Mapping[str, object] | None) -> tuple[str, str]:
    if triage is None:
        return "missing", "Symptom onset has not been assessed."
    state = _text(triage.get("symptom_onset_state"), "not_assessed")
    if state in _UNCERTAIN_STATES:
        return "missing", "Symptom onset is unknown or not assessed."
    if state == "present" and triage.get("symptom_onset_at") is None:
        return "missing", "Symptom onset is present but no onset time is recorded."
    return "current", "Symptom onset has explicit documentation."


def _risk_factor_status(triage: Mapping[str, object] | None) -> tuple[str, str]:
    if triage is None:
        return "missing", "Cardiovascular risk factors have not been assessed."
    raw_observations = triage.get("observations", [])
    observation_values = raw_observations if isinstance(raw_observations, list | tuple) else ()
    observations = [
        item
        for item in observation_values
        if isinstance(item, Mapping)
        and _text(item.get("category")) == "cardiovascular_risk_factor"
    ]
    if not observations:
        return "missing", "Cardiovascular risk factors are not documented."
    states = {_text(item.get("state")) for item in observations}
    if states <= _UNCERTAIN_STATES:
        return "missing", "Cardiovascular risk factors are only unknown or not assessed."
    return "current", "Cardiovascular risk factors have explicit present/absent documentation."


def _status_from_presence(present: bool, missing_reason: str) -> tuple[str, str]:
    if present:
        return "current", "Evidence is currently available."
    return "missing", missing_reason


def _task_type_for_gap(evidence_type: str) -> str:
    if evidence_type == "ecg":
        return "repeat_ecg"
    if evidence_type == "troponin":
        return "repeat_troponin"
    if evidence_type == "unresolved_alert":
        return "physician_review"
    return "obtain_additional_information"


def _due_state_for(task_type: str, gaps: Sequence[Mapping[str, object]]) -> str:
    statuses = {_text(gap.get("status")) for gap in gaps}
    if task_type in {"repeat_ecg", "physician_review"} or "technical_limit" in statuses:
        return "due_now"
    return "due_soon"


def _due_at_for(now: datetime, due_state: str) -> datetime:
    if due_state == "due_now":
        return now
    return now + timedelta(minutes=30)


def _ecg_has_technical_limit(ecg: Mapping[str, object] | None, limits: Sequence[str]) -> bool:
    quality = _text(ecg.get("quality_status") if ecg else None)
    return quality in {"limited", "poor", "insufficient", "unsupported", "failed", "unusable"} or any(
        "ecg" in item.lower() for item in limits
    )


def _canonical_name(value: str) -> str:
    normalized = value.lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "risk_factor": "risk_factors",
        "cardiovascular_risk_factor": "risk_factors",
        "cardiovascular_risk_factors": "risk_factors",
        "symptom_onset_time": "symptom_onset",
    }
    return aliases.get(normalized, normalized)


def _default_missing_reason(name: str) -> str:
    return f"{_label(name)} is missing or unknown."


def _label(name: str) -> str:
    return name.replace("_", " ").title()


def _due_rank(value: str) -> int:
    return {"overdue": 0, "due_now": 1, "due_soon": 2}.get(value, 3)


def _severity_rank(value: str) -> int:
    return {"critical": 4, "urgent": 3, "review": 2, "information": 1}.get(value, 0)


def _datetime_sort_key(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


def _text(value: object, fallback: str = "") -> str:
    return str(value) if value is not None and str(value) else fallback


def _optional_text(value: object) -> str | None:
    text = _text(value)
    return text or None


def _int(value: object) -> int:
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0
