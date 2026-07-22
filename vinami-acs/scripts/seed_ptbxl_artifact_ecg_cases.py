"""Seed five PTB-XL artifact-backed ECG showcase cases through the public API."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import exp, sin
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

LABELS = ("NORM", "MI", "STTC", "CD", "HYP")
LEADS = ("I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6")
DISPLAY_LABELS = {
    "NORM": "NORM reference ECG pattern",
    "MI": "MI-related ECG pattern showcase",
    "STTC": "ST/T change showcase",
    "CD": "Conduction-disturbance showcase",
    "HYP": "Hypertrophy-pattern showcase",
}
BASE_TIME = datetime(2026, 7, 17, 9, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class RepresentativeSample:
    label: str
    ecg_id: int
    record_path: str
    raw_preview: Path | None
    spatial_preview: Path | None


def main() -> None:
    args = _parse_args()
    samples = _read_representative_samples(args.artifact_root)
    created: list[dict[str, Any]] = []
    with httpx.Client(base_url=args.api_base_url, timeout=30.0) as client:
        _ensure_api_available(client)
        for index, sample in enumerate(samples):
            created.append(
                _seed_case(
                    client,
                    sample,
                    index=index,
                    run_id=args.run_id,
                    location=args.location,
                    ui_base_url=args.ui_base_url,
                    provider_name=args.provider,
                    fallback_provider=args.fallback_provider,
                    record_physician_review=not args.skip_physician_review,
                )
            )
    print(
        json.dumps(
            {
                "seeded_cases": created,
                "run_id": args.run_id,
                "location": args.location,
                "provider_requested": args.provider,
                "artifact_root": str(args.artifact_root),
                "safety_notice": (
                    "PTB-XL artifact-backed demo cases are for research UI validation only; "
                    "model scores are not diagnoses or clinical probabilities."
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )


def _parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2] / "VinStroke_ECG_artifacts"
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--ui-base-url", default="http://127.0.0.1:3000")
    parser.add_argument("--artifact-root", type=Path, default=root)
    parser.add_argument("--run-id", default="r23a-visible")
    parser.add_argument("--location", default="Emergency Department")
    parser.add_argument("--provider", default="mock")
    parser.add_argument("--fallback-provider", default="mock")
    parser.add_argument("--skip-physician-review", action="store_true")
    return parser.parse_args()


def _ensure_api_available(client: httpx.Client) -> None:
    response = client.get("/ready")
    if response.status_code != 200:
        raise RuntimeError(f"VinAMI API is not ready: {response.status_code} {response.text}")


def _read_representative_samples(root: Path) -> tuple[RepresentativeSample, ...]:
    manifest = root / "reports" / "r23a_golden_samples.csv"
    if not manifest.is_file():
        manifest = root / "reports" / "representative_samples.csv"
    if not manifest.is_file():
        raise FileNotFoundError(f"representative sample manifest not found: {manifest}")
    rows: dict[str, RepresentativeSample] = {}
    with manifest.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            label = str(row.get("label", "")).strip()
            if label not in LABELS:
                continue
            ecg_id = int(str(row["ecg_id"]))
            rows[label] = RepresentativeSample(
                label=label,
                ecg_id=ecg_id,
                record_path=str(row.get("record_path", "")),
                raw_preview=_preview(root, "raw_12lead", label, ecg_id),
                spatial_preview=_preview(root, "spatial_12lead", label, ecg_id),
            )
    missing = [label for label in LABELS if label not in rows]
    if missing:
        raise RuntimeError(f"representative sample manifest is incomplete: {', '.join(missing)}")
    return tuple(rows[label] for label in LABELS)


def _preview(root: Path, prefix: str, label: str, ecg_id: int) -> Path | None:
    value = root / "reports" / f"{prefix}_{label}_ecg{ecg_id}.png"
    return value if value.is_file() else None


def _seed_case(
    client: httpx.Client,
    sample: RepresentativeSample,
    *,
    index: int,
    run_id: str,
    location: str,
    ui_base_url: str,
    provider_name: str,
    fallback_provider: str,
    record_physician_review: bool,
) -> dict[str, Any]:
    safe_run_id = _safe_slug(run_id)
    slug = f"ptbxl-{safe_run_id}-{sample.label.lower()}-{sample.ecg_id:05d}"
    patient = _post(
        client,
        "/api/v1/patients",
        identity="nurse",
        key=f"{slug}-patient",
        json_body={
            "patient_reference": f"PTBXL-{safe_run_id.upper()}-{sample.label}-{sample.ecg_id:05d}",
            "safe_demographic_summary": {
                "age_band": "research-demo",
                "sex_at_birth": "unknown",
            },
        },
    )
    encounter = _post(
        client,
        "/api/v1/encounters",
        identity="nurse",
        key=f"{slug}-encounter",
        json_body={
            "patient_id": patient["patient_id"],
            "location": location,
            "arrival_at": (BASE_TIME + timedelta(minutes=index * 11)).isoformat(),
            "external_reference": f"PTBXL-{safe_run_id.upper()}-ENC-{sample.ecg_id:05d}",
        },
    )
    clinical_case = _post(
        client,
        "/api/v1/clinical-cases",
        identity="physician",
        key=f"{slug}-case",
        json_body={
            "encounter_id": encounter["encounter_id"],
            "opening_reason": (
                f"R23A ECG artifact showcase using representative PTB-XL {sample.label} record "
                f"{sample.ecg_id}. Demonstration rule - not for clinical use."
            ),
            "priority": "urgent" if sample.label in {"MI", "STTC"} else "routine",
        },
    )
    _record_triage(client, slug, clinical_case, sample, index)
    _record_vitals(client, slug, clinical_case, index)
    study_id = _record_ecg(client, slug, clinical_case, sample, index)
    analysis = _request_analysis(client, slug, study_id, provider_name, fallback_provider)
    interpretation_id = None
    if record_physician_review:
        interpretation_id = _record_interpretation(client, slug, study_id, analysis, sample, index)
    return {
        "label": sample.label,
        "ecg_id": sample.ecg_id,
        "patient_id": patient["patient_id"],
        "case_id": clinical_case["case_id"],
        "study_id": study_id,
        "analysis_id": analysis["analysis_id"],
        "analysis_status": analysis["status"],
        "provider_name": analysis["provider_name"],
        "synthetic_provider": analysis["synthetic"],
        "physician_interpretation_id": interpretation_id,
        "ui_case_url": f"{ui_base_url.rstrip('/')}/cases/{clinical_case['case_id']}",
        "ui_ecg_url": f"{ui_base_url.rstrip('/')}/cases/{clinical_case['case_id']}/ecg",
        "api_workspace_url": (
            f"{str(client.base_url).rstrip('/')}/api/v1/clinical-cases/"
            f"{clinical_case['case_id']}/complete-workspace"
        ),
    }


def _record_triage(
    client: httpx.Client,
    slug: str,
    clinical_case: dict[str, Any],
    sample: RepresentativeSample,
    index: int,
) -> None:
    case_id = str(clinical_case["case_id"])
    _post(
        client,
        f"/api/v1/clinical-cases/{case_id}/triage-assessments",
        identity="nurse",
        key=f"{slug}-triage",
        json_body={
            "expected_case_version": int(clinical_case["aggregate_version"]),
            "occurred_at": (BASE_TIME + timedelta(minutes=index * 11 + 2)).isoformat(),
            "source": "ptbxl-r23a-seed-script",
            "chief_complaint": (
                f"Research ECG showcase case for {DISPLAY_LABELS[sample.label]}; "
                "not a real patient presentation."
            ),
            "symptom_onset_state": "unknown",
            "symptom_onset_at": None,
            "symptom_onset_precision": "unknown",
            "symptom_description": (
                "Synthetic workflow context only. Missing symptom onset remains unknown, "
                "not negative evidence."
            ),
            "associated_symptoms": [{"name": "chest discomfort", "state": "unknown"}],
            "cardiovascular_risk_factors": [{"name": "risk factor history", "state": "unknown"}],
        },
    )


def _record_vitals(
    client: httpx.Client,
    slug: str,
    clinical_case: dict[str, Any],
    index: int,
) -> None:
    observed_at = BASE_TIME + timedelta(minutes=index * 11 + 3)
    measurements = (
        ("heart_rate", 76 + index * 3, "beats/min"),
        ("systolic_blood_pressure", 124 + index * 4, "mmHg"),
        ("diastolic_blood_pressure", 74 + index * 2, "mmHg"),
        ("oxygen_saturation", 98, "%"),
        ("body_temperature", 36.7, "degC"),
    )
    _post(
        client,
        f"/api/v1/clinical-cases/{clinical_case['case_id']}/vital-observation-sets",
        identity="nurse",
        key=f"{slug}-vitals",
        json_body={
            "expected_case_version": int(clinical_case["aggregate_version"]),
            "observed_at": observed_at.isoformat(),
            "source": "ptbxl-r23a-seed-script",
            "supplemental_oxygen_state": "unknown",
            "measurements": [
                {
                    "kind": kind,
                    "value": value,
                    "unit": unit,
                    "source": "research-demo-entry",
                    "observed_at": observed_at.isoformat(),
                    "quality_status": "accepted",
                }
                for kind, value, unit in measurements
            ],
        },
    )


def _record_ecg(
    client: httpx.Client,
    slug: str,
    clinical_case: dict[str, Any],
    sample: RepresentativeSample,
    index: int,
) -> str:
    reference = f"{slug.upper()}-{sample.label}-{sample.ecg_id:05d}"
    waveform = _representative_waveform(reference, sample)
    response = client.post(
        f"/api/v1/clinical-cases/{clinical_case['case_id']}/ecg-studies",
        headers=_headers(f"{slug}-ecg-upload", "nurse"),
        data={
            "source_type": "canonical_waveform",
            "study_reference": reference,
            "acquisition_at": (BASE_TIME + timedelta(minutes=index * 11 + 5)).isoformat(),
            "content_type": "application/vnd.vinami.ecg+json",
            "expected_case_version": str(clinical_case["aggregate_version"]),
        },
        files={
            "artifact": (
                f"{reference}.json",
                json.dumps(waveform, separators=(",", ":"), sort_keys=True).encode(),
                "application/vnd.vinami.ecg+json",
            )
        },
    )
    _raise_for_status(response, "record ECG")
    return str(response.json()["resulting_study_id"])


def _request_analysis(
    client: httpx.Client,
    slug: str,
    study_id: str,
    provider_name: str,
    fallback_provider: str,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/ecg-studies/{study_id}/analyses",
        headers=_headers(f"{slug}-analysis-{provider_name}", "physician"),
        json={"provider_name": provider_name},
    )
    if response.status_code == 409 and fallback_provider and fallback_provider != provider_name:
        response = client.post(
            f"/api/v1/ecg-studies/{study_id}/analyses",
            headers=_headers(f"{slug}-analysis-{fallback_provider}", "physician"),
            json={"provider_name": fallback_provider},
        )
    _raise_for_status(response, "request ECG analysis")
    return dict(response.json())


def _record_interpretation(
    client: httpx.Client,
    slug: str,
    study_id: str,
    analysis: dict[str, Any],
    sample: RepresentativeSample,
    index: int,
) -> str:
    response = _post(
        client,
        f"/api/v1/ecg-studies/{study_id}/physician-interpretations",
        identity="physician",
        key=f"{slug}-interpretation",
        json_body={
            "analysis_id": analysis["analysis_id"],
            "interpretation_status": "reviewed",
            "structured_interpretation": (
                f"Physician review placeholder for R23A UI demonstration: PTB-XL "
                f"representative label {sample.label}, ECG {sample.ecg_id}. "
                "This is not a clinical diagnosis."
            ),
            "agreement_status": "requires_clinical_correlation",
            "quality_disposition": "acceptable_for_review",
            "repeat_ecg_requested": False,
            "note": (
                "AI-supported ECG finding is a model-score aid only; "
                "physician authority remains required."
            ),
            "occurred_at": (BASE_TIME + timedelta(minutes=index * 11 + 8)).isoformat(),
            "expected_version": 0,
        },
    )
    return str(response["interpretation_id"])


def _representative_waveform(reference: str, sample: RepresentativeSample) -> dict[str, Any]:
    sampling_rate = 100
    preview_notes = [
        f"PTB-XL representative label metadata: {sample.label}, ecg_id={sample.ecg_id}.",
        f"Original manifest record path: {sample.record_path}.",
        (
            "Local artifact package does not include WFDB .dat/.hea waveform files; this "
            "canonical waveform is a deterministic UI/integration surrogate."
        ),
    ]
    if sample.raw_preview is not None:
        preview_notes.append(f"Raw ECG report preview artifact: {sample.raw_preview.name}.")
    if sample.spatial_preview is not None:
        preview_notes.append(f"Spatial ECG report preview artifact: {sample.spatial_preview.name}.")
    return {
        "schema_version": "1.0",
        "study_reference": reference,
        "sampling_rate_hz": sampling_rate,
        "amplitude_unit": "uV",
        "source_device": "PTB-XL R23A artifact-backed seed surrogate",
        "calibration": "10 mm/mV",
        "lead_order": list(LEADS),
        "parser_warnings": preview_notes,
        "leads": [
            {"name": lead, "samples": _lead_samples(sample.label, lead_index, sample.ecg_id)}
            for lead_index, lead in enumerate(LEADS)
        ],
    }


def _lead_samples(label: str, lead_index: int, ecg_id: int) -> list[int]:
    values: list[int] = []
    lead_gain = (0.92, 1.0, 0.78, -0.58, 0.66, 0.74, 0.70, 0.94, 1.06, 1.0, 0.9, 0.84)[
        lead_index
    ]
    period = 94 + (ecg_id % 9)
    if label == "CD":
        period += 8
    amplitude = 690.0 * abs(lead_gain)
    if label == "HYP" and lead_index in {8, 9, 10, 11}:
        amplitude *= 1.55
    if label == "MI" and lead_index in {7, 8, 9}:
        amplitude *= 0.78
    polarity = -1.0 if lead_gain < 0 else 1.0
    for position in range(1000):
        beat_position = position + ecg_id * 3 + lead_index * 2
        phase = (beat_position % period) / period
        baseline = 30.0 * sin(position / 53.0 + lead_index * 0.31) + 10.0 * sin(
            position / 17.0 + ecg_id * 0.07
        )
        p_wave = polarity * 44.0 * exp(-(((phase - 0.18) / 0.045) ** 2))
        q_wave = -polarity * 80.0 * exp(-(((phase - 0.43) / 0.018) ** 2))
        qrs_width = 0.023 if label != "CD" else 0.052
        qrs = polarity * amplitude * exp(-(((phase - 0.48) / qrs_width) ** 2))
        if label == "CD":
            qrs += polarity * amplitude * 0.42 * exp(-(((phase - 0.545) / 0.045) ** 2))
        s_wave = -polarity * 165.0 * exp(-(((phase - 0.535) / 0.028) ** 2))
        t_wave = polarity * 115.0 * exp(-(((phase - 0.72) / 0.12) ** 2))
        if label == "STTC" and lead_index in {6, 7, 8, 9}:
            t_wave *= -1.05
        if label == "HYP" and lead_index in {8, 9, 10, 11}:
            t_wave *= -0.65
        if label == "MI" and lead_index in {7, 8, 9}:
            q_wave *= 1.85
        st_shift = 0.0
        if label == "MI" and lead_index in {6, 7, 8, 9} and 0.54 <= phase <= 0.68:
            st_shift = polarity * 120.0
        if label == "STTC" and lead_index in {1, 6, 7, 8, 9, 10} and 0.54 <= phase <= 0.68:
            st_shift = -polarity * 75.0
        if label == "HYP" and lead_index in {8, 9, 10, 11} and 0.54 <= phase <= 0.68:
            st_shift = -polarity * 95.0
        artifact_texture = 9.0 * sin(position / 5.2 + lead_index) + 5.0 * sin(
            position / 2.9 + ecg_id * 0.13
        )
        value = baseline + p_wave + q_wave + qrs + s_wave + t_wave + st_shift + artifact_texture
        values.append(int(round(value)))
    return values


def _post(
    client: httpx.Client,
    path: str,
    *,
    identity: str,
    key: str,
    json_body: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(path, headers=_headers(key, identity), json=json_body)
    _raise_for_status(response, path)
    return dict(response.json())


def _headers(key: str, identity: str) -> dict[str, str]:
    return {
        "X-Development-Identity": identity,
        "X-Correlation-ID": str(uuid4()),
        "X-Request-Source": "seed-ptbxl-artifact-ecg-cases",
        "Idempotency-Key": key,
    }


def _safe_slug(value: str) -> str:
    cleaned = "".join(
        character.lower() if character.isalnum() else "-" for character in value.strip()
    ).strip("-")
    return cleaned or "r23a-visible"


def _raise_for_status(response: httpx.Response, action: str) -> None:
    if response.status_code not in {200, 201}:
        raise RuntimeError(f"{action} failed: {response.status_code} {response.text}")


if __name__ == "__main__":
    main()
