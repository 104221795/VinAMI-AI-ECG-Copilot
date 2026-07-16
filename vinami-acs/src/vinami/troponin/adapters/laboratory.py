"""Deterministic local/mock laboratory connector; this is not a live LIS adapter."""

from __future__ import annotations

from vinami.troponin.ports.laboratory import (
    LaboratoryPayloadError,
    LaboratoryTimeoutError,
    LaboratoryUnavailableError,
)


class MockLaboratoryConnector:
    connector_id = "mock-lab-r4"
    connector_type = "deterministic_local_profile"

    def capabilities(self) -> tuple[str, ...]:
        return (
            "fetch_result",
            "source_delivery_revisions",
            "preliminary",
            "final",
            "amendment",
            "deterministic_retry",
        )

    def health(self) -> dict[str, object]:
        return {"status": "available", "live_lis": False, "profile": "vinami-local-lab-result-v1"}

    def source_info(self) -> dict[str, str]:
        return {
            "name": "VinAMI deterministic mock laboratory",
            "profile": "vinami-local-lab-result-v1",
            "version": "1",
        }

    def fetch_result(self, reference: str) -> dict[str, object]:
        mode = reference.strip().lower()
        if mode in {"unavailable", "retry-success"}:
            raise LaboratoryUnavailableError(
                "The local mock connector is unavailable for this request."
            )
        if mode == "timeout":
            raise LaboratoryTimeoutError("The local mock connector timed out.")
        if mode in {"not-found", "malformed"}:
            raise LaboratoryPayloadError(
                "The requested local laboratory result could not be parsed."
            )
        payload: dict[str, object] = {
            "external_result_id": f"mock-{mode}",
            "source_identity": f"mock-{mode}",
            "source_revision": 1,
            "assay_code": "DEMO-HS-CTNI-01",
            "analyte": "cardiac_troponin_i",
            "value": "12.40",
            "unit": "ng/L",
            "status": "final",
            "specimen_type": "plasma",
            "reference_limit": "19",
            "reference_limit_unit": "ng/L",
            "quality_flags": [],
        }
        lifecycle_modes = {
            "preliminary": ("preliminary", 1, "12.40"),
            "duplicate-preliminary": ("preliminary", 1, "12.40"),
            "final": ("final", 2, "12.40"),
            "duplicate-final": ("final", 2, "12.40"),
            "amended": ("amended", 3, "12.60"),
            "duplicate-amended": ("amended", 3, "12.60"),
        }
        if mode in lifecycle_modes:
            status, revision, value = lifecycle_modes[mode]
            payload.update(
                {
                    "external_result_id": "mock-lifecycle-ctni-001",
                    "source_identity": "mock-lifecycle-ctni-001",
                    "source_revision": revision,
                    "status": status,
                    "value": value,
                    "accession_number": "MOCK-ACC-001",
                    "specimen_id": "MOCK-SPECIMEN-001",
                }
            )
            if revision > 1:
                payload["supersedes_source_revision"] = revision - 1
            if status == "amended":
                payload["source_amendment_reason"] = "Deterministic local mock correction."
        if mode == "missing-unit":
            payload.pop("unit")
        if mode == "missing-reference-limit":
            payload.pop("reference_limit")
            payload.pop("reference_limit_unit")
        if mode == "unsupported-assay":
            payload["assay_code"] = "UNKNOWN-LAB-ASSAY"
        return payload

    def parse_result(self, payload: dict[str, object]) -> dict[str, object]:
        required = ("external_result_id", "assay_code", "analyte", "value", "unit", "status")
        missing = [key for key in required if key not in payload]
        if missing:
            raise LaboratoryPayloadError(
                f"Local laboratory profile is missing: {', '.join(missing)}"
            )
        return dict(payload)
