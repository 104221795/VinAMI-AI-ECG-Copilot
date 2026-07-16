"""Focused R4.1 API acceptance coverage for immutable troponin evidence."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from apps.api.app import create_app
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from tests.integration.test_r3_ecg_api import NOW, _case, _headers, _settings


def _record(
    client: TestClient, case_id: str, case_version: int, *, minute: int, source: str
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/clinical-cases/{case_id}/troponin-results",
        headers=_headers(f"r4-result-{source}-{uuid4()}", "physician"),
        json={
            "assay_code": "DEMO-HS-CTNI-01",
            "analyte": "cardiac_troponin_i",
            "value": "12.40",
            "unit": "ng/L",
            "specimen_type": "plasma",
            "specimen_collected_at": (NOW + timedelta(minutes=minute)).isoformat(),
            "resulted_at": (NOW + timedelta(minutes=minute + 1)).isoformat(),
            "result_status": "final",
            "quality_flags": [],
            "source_system": "r4-api-test",
            "source_result_id": source,
            "expected_case_version": case_version,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _import(
    client: TestClient, case_id: str, case_version: int, reference: str
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/clinical-cases/{case_id}/troponin-imports",
        headers=_headers(f"r4-import-{reference}-{uuid4()}", "physician"),
        json={
            "connector_id": "mock-lab-r4",
            "external_reference": reference,
            "expected_case_version": case_version,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_r4_1_lifecycle_repeat_review_correction_and_unit_contract(
    postgres_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    _ = postgres_session_factory
    with TestClient(create_app(_settings(tmp_path / "r4-troponin"))) as client:
        clinical_case = _case(client)
        case_id = str(clinical_case["case_id"])
        case_version = int(clinical_case["aggregate_version"])

        preliminary = _import(client, case_id, case_version, "preliminary")
        final = _import(client, case_id, case_version, "final")
        amended = _import(client, case_id, case_version, "amended")
        duplicate = _import(client, case_id, case_version, "duplicate-amended")
        assert preliminary["status"] == final["status"] == amended["status"] == "completed"
        assert duplicate["status"] == "completed_with_warning"

        workspace = client.get(
            f"/api/v1/clinical-cases/{case_id}/troponin-workspace", headers=_headers()
        )
        assert workspace.status_code == 200
        history = workspace.json()["result_history"]
        lifecycle = [
            item for item in history if item["source_identity"] == "mock-lifecycle-ctni-001"
        ]
        assert [item["source_revision"] for item in lifecycle] == [1, 2, 3]
        assert lifecycle[1]["supersedes_result_id"] == lifecycle[0]["result_id"]
        assert lifecycle[2]["supersedes_result_id"] == lifecycle[1]["result_id"]
        assert any(
            item["result_id"] == lifecycle[2]["result_id"]
            for item in workspace.json()["effective_results"]
        )

        source = _record(client, case_id, case_version, minute=10, source="repeat-source")
        completed = _record(client, case_id, case_version, minute=20, source="repeat-completed")
        review = client.post(
            f"/api/v1/clinical-cases/{case_id}/troponin-reviews",
            headers=_headers(f"r4-review-{uuid4()}", "physician"),
            json={
                "referenced_result_ids": [source["result_id"]],
                "review_status": "evidence_reviewed",
                "incompatibility_acknowledged": False,
                "quality_limitation_acknowledged": False,
                "repeat_measurement_requested": True,
                "repeat_measurement_reason": "Synthetic serial evidence follow-up.",
                "note": "Original immutable review.",
                "occurred_at": NOW.isoformat(),
                "expected_case_version": case_version,
            },
        )
        assert review.status_code == 201, review.text
        request_id = review.json()["repeat_request"]["request_id"]
        request_version = review.json()["repeat_request"]["record_version"]
        acknowledged = client.post(
            f"/api/v1/repeat-troponin-requests/{request_id}/acknowledge",
            headers=_headers(f"r4-ack-{uuid4()}", "physician"),
            json={"expected_version": request_version},
        )
        assert acknowledged.status_code == 200, acknowledged.text
        completed_request = client.post(
            f"/api/v1/repeat-troponin-requests/{request_id}/complete",
            headers=_headers(f"r4-complete-{uuid4()}", "physician"),
            json={
                "expected_version": acknowledged.json()["record_version"],
                "completed_result_id": completed["result_id"],
            },
        )
        assert completed_request.status_code == 200, completed_request.text
        assert completed_request.json()["status"] == "completed"

        correction = client.post(
            f"/api/v1/clinical-cases/{case_id}/troponin-reviews/{review.json()['review_id']}/corrections",
            headers=_headers(f"r4-correction-{uuid4()}", "physician"),
            json={
                "correction_reason": "Clarified synthetic evidence note.",
                "referenced_result_ids": [source["result_id"]],
                "review_status": "evidence_reviewed",
                "incompatibility_acknowledged": False,
                "quality_limitation_acknowledged": False,
                "repeat_measurement_requested": True,
                "repeat_measurement_reason": "Synthetic serial evidence follow-up.",
                "corrected_note": "Corrected immutable review.",
                "occurred_at": NOW.isoformat(),
                "expected_case_version": case_version,
                "expected_review_version": review.json()["record_version"],
            },
        )
        assert correction.status_code == 201, correction.text
        reviews = client.get(
            f"/api/v1/clinical-cases/{case_id}/troponin-reviews", headers=_headers()
        ).json()
        assert len(reviews) == 2
        assert reviews[1]["supersedes_review_id"] == review.json()["review_id"]
        assert reviews[0]["note"] == "Original immutable review."

        unsupported = client.post(
            f"/api/v1/clinical-cases/{case_id}/troponin-results",
            headers=_headers(f"r4-unit-{uuid4()}", "physician"),
            json={
                "assay_code": "DEMO-HS-CTNI-01",
                "analyte": "cardiac_troponin_i",
                "value": "1",
                "unit": "mg/dL",
                "specimen_type": "plasma",
                "specimen_collected_at": NOW.isoformat(),
                "resulted_at": NOW.isoformat(),
                "result_status": "final",
                "quality_flags": [],
                "source_system": "r4-api-test",
                "source_result_id": str(uuid4()),
                "expected_case_version": case_version,
            },
        )
        assert unsupported.status_code == 422
        assert unsupported.headers["content-type"].startswith("application/problem+json")
        assert unsupported.json()["errors"] == [{"field": "unit", "code": "unsupported_unit"}]


def test_r4_1_idempotency_amendment_retry_and_rejection_paths(
    postgres_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    _ = postgres_session_factory
    with TestClient(create_app(_settings(tmp_path / "r4-commands"))) as client:
        clinical_case = _case(client)
        case_id = str(clinical_case["case_id"])
        case_version = int(clinical_case["aggregate_version"])
        source_id = f"idempotent-{uuid4()}"
        key = f"r4-record-{uuid4()}"
        body = {
            "assay_code": "DEMO-HS-CTNI-01",
            "analyte": "cardiac_troponin_i",
            "value": "10",
            "unit": "ng/L",
            "specimen_type": "plasma",
            "specimen_collected_at": NOW.isoformat(),
            "resulted_at": NOW.isoformat(),
            "result_status": "final",
            "quality_flags": [],
            "source_system": "r4-idempotency",
            "source_result_id": source_id,
            "expected_case_version": case_version,
        }
        first = client.post(
            f"/api/v1/clinical-cases/{case_id}/troponin-results",
            headers=_headers(key, "physician"),
            json=body,
        )
        assert first.status_code == 201, first.text
        duplicate = client.post(
            f"/api/v1/clinical-cases/{case_id}/troponin-results",
            headers=_headers(key, "physician"),
            json=body,
        )
        assert duplicate.status_code == 201
        assert duplicate.json()["result_id"] == first.json()["result_id"]
        key_conflict = client.post(
            f"/api/v1/clinical-cases/{case_id}/troponin-results",
            headers=_headers(key, "physician"),
            json={**body, "value": "11"},
        )
        assert key_conflict.status_code == 409

        amended = client.post(
            f"/api/v1/troponin-results/{first.json()['result_id']}/amendments",
            headers=_headers(f"r4-amend-{uuid4()}", "physician"),
            json={
                "value": "11",
                "unit": "ng/L",
                "result_status": "amended",
                "amendment_reason": "Corrected synthetic value.",
                "resulted_at": NOW.isoformat(),
                "expected_version": first.json()["record_version"],
            },
        )
        assert amended.status_code == 201, amended.text
        stale = client.post(
            f"/api/v1/troponin-results/{first.json()['result_id']}/amendments",
            headers=_headers(f"r4-stale-{uuid4()}", "physician"),
            json={
                "value": "11",
                "unit": "ng/L",
                "result_status": "amended",
                "amendment_reason": "Stale synthetic request.",
                "resulted_at": NOW.isoformat(),
                "expected_version": 99,
            },
        )
        assert stale.status_code == 409

        failed = _import(client, case_id, case_version, "retry-success")
        assert failed["status"] == "failed"
        retry = client.post(
            f"/api/v1/laboratory-import-jobs/{failed['import_job_id']}/retry",
            headers=_headers(f"r4-retry-{uuid4()}", "physician"),
            json={"expected_version": failed["record_version"]},
        )
        assert retry.status_code == 200, retry.text
        assert retry.json()["status"] == "completed"

        missing = client.post(
            f"/api/v1/clinical-cases/{case_id}/troponin-results",
            headers=_headers(f"r4-missing-unit-{uuid4()}", "physician"),
            json={key: value for key, value in body.items() if key != "unit"},
        )
        assert missing.status_code == 422
        assert missing.json()["errors"] == [{"field": "unit", "code": "unit_required"}]
        malformed = client.post(
            f"/api/v1/clinical-cases/{case_id}/troponin-results",
            headers=_headers(f"r4-malformed-unit-{uuid4()}", "physician"),
            json={**body, "source_result_id": f"bad-unit-{uuid4()}", "unit": "ng//L"},
        )
        assert malformed.status_code == 422
        assert malformed.json()["errors"][0]["field"] == "unit"
