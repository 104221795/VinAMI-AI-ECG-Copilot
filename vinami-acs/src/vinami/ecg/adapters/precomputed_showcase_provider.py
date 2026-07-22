"""PTB-XL R23A showcase provider backed by precomputed best-checkpoint artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from vinami.ecg.ports.provider import (
    AIProviderHealth,
    ECGExplanationRequest,
    ECGExplanationResult,
    ECGPredictionRequest,
    ECGPredictionResult,
    InputValidationResult,
    ModelInfo,
)

LABEL_ORDER = ("NORM", "MI", "STTC", "CD", "HYP")
PROVIDER_NAME = "ptbxl-r23a-precomputed-best-pt-showcase"
INPUT_CONTRACT = (
    "Precomputed R23A showcase generated from the verified PTB-XL ConvNeXtV2 "
    "best_model.pt checkpoint. Requests are matched to PTB-XL representative "
    "metadata carried in the canonical waveform artifact."
)


@dataclass(frozen=True, slots=True)
class _ShowcaseEntry:
    label: str
    ecg_id: int
    model_name: str
    model_version: str
    checkpoint_checksum: str
    preprocessing_version: str
    threshold_source: str
    label_scores: dict[str, float]
    thresholds: dict[str, float]
    predicted_findings: tuple[str, ...]
    explanation_label: str
    explanation_image: Path
    warnings: tuple[str, ...]
    provenance: dict[str, str]


class PTBXLShowcaseProvider:
    """Serve deterministic best-checkpoint PTB-XL showcase outputs without torch at runtime."""

    def __init__(self, manifest_path: Path, artifact_root: Path | None = None) -> None:
        self._manifest_path = manifest_path.resolve()
        self._artifact_root = (artifact_root or self._manifest_path.parents[1]).resolve()
        self._manifest: dict[str, Any] | None = None
        self._entries: dict[tuple[str, int], _ShowcaseEntry] | None = None

    def get_model_info(self) -> ModelInfo:
        manifest = self._load_manifest()
        return ModelInfo(
            name=str(manifest["model_name"]),
            version=str(manifest["model_version"]),
            provider_name=PROVIDER_NAME,
            input_contract=INPUT_CONTRACT,
            synthetic=False,
            checkpoint_checksum=str(manifest["checkpoint_sha256"]),
            label_order=tuple(str(item) for item in manifest["label_order"]),
            threshold_source=str(manifest["threshold_source"]),
        )

    def health(self) -> AIProviderHealth:
        try:
            entries = self._load_entries()
        except Exception as error:
            return AIProviderHealth(
                False,
                PROVIDER_NAME,
                f"unavailable: {type(error).__name__}: {_safe_text(str(error))}",
            )
        return AIProviderHealth(
            True,
            PROVIDER_NAME,
            f"{len(entries)} precomputed best-checkpoint showcase entries available",
        )

    def validate_input(self, request: ECGPredictionRequest) -> InputValidationResult:
        if request.input_quality in {"poor", "insufficient", "unsupported", "failed"}:
            return InputValidationResult(
                False,
                ("Technical ECG quality blocks normal model-score presentation.",),
                "technical ECG quality blocks analysis",
            )
        if request.waveform_bytes is None:
            return InputValidationResult(
                False,
                failure_reason="PTB-XL showcase provider requires canonical waveform metadata",
            )
        try:
            self._key_from_waveform(request.waveform_bytes)
        except ValueError as error:
            return InputValidationResult(False, failure_reason=str(error))
        return InputValidationResult(True)

    def predict(self, request: ECGPredictionRequest) -> ECGPredictionResult:
        validation = self.validate_input(request)
        started = datetime.now(UTC)
        if not validation.valid:
            completed = datetime.now(UTC)
            info = self.get_model_info()
            return ECGPredictionResult(
                request.study_id,
                info.name,
                info.version,
                info.provider_name,
                started,
                completed,
                request.input_quality,
                {},
                {},
                (),
                (),
                validation.warnings,
                {"validation_status": "rejected"},
                validation.failure_reason,
                info.synthetic,
            )
        entry = self._entry_for_request(request)
        completed = datetime.now(UTC)
        return ECGPredictionResult(
            request.study_id,
            entry.model_name,
            entry.model_version,
            PROVIDER_NAME,
            started,
            completed,
            request.input_quality,
            entry.label_scores,
            entry.thresholds,
            entry.predicted_findings,
            (f"artifact://ptbxl-r23a-gradcam/{entry.label}/{entry.ecg_id}",),
            _dedupe(
                (
                    "Precomputed best_model.pt showcase output; not a diagnosis "
                    "or clinical probability.",
                    *validation.warnings,
                    *entry.warnings,
                )
            ),
            {
                **entry.provenance,
                "input_artifact_checksum": request.artifact_checksum or "unavailable",
                "manifest_sha256": _file_sha256(self._manifest_path),
                "provider_kind": "precomputed-real-checkpoint-showcase",
            },
            None,
            False,
        )

    def explain(self, request: ECGExplanationRequest) -> ECGExplanationResult:
        entry = self._entry_for_waveform(request.waveform_bytes)
        if request.target_label != entry.explanation_label:
            return ECGExplanationResult(
                request.study_id,
                request.target_label,
                "unavailable",
                (
                    "Precomputed Grad-CAM artifact is available only for the stored "
                    f"showcase target label {entry.explanation_label}."
                ),
                synthetic=False,
            )
        if not entry.explanation_image.is_file():
            return ECGExplanationResult(
                request.study_id,
                request.target_label,
                "unavailable",
                "Precomputed Grad-CAM image is missing from the PTB-XL artifact bundle.",
                synthetic=False,
            )
        return ECGExplanationResult(
            request.study_id,
            request.target_label,
            f"artifact://ptbxl-r23a-gradcam/{entry.label}/{entry.ecg_id}",
            "Grad-CAM is a model-attention aid; not causal clinical evidence.",
            entry.explanation_image.read_bytes(),
            "image/png",
            False,
        )

    def _entry_for_request(self, request: ECGPredictionRequest) -> _ShowcaseEntry:
        return self._entry_for_waveform(request.waveform_bytes)

    def _entry_for_waveform(self, waveform_bytes: bytes | None) -> _ShowcaseEntry:
        if waveform_bytes is None:
            raise ValueError("canonical waveform bytes are required for showcase lookup")
        key = self._key_from_waveform(waveform_bytes)
        try:
            return self._load_entries()[key]
        except KeyError as error:
            raise ValueError(
                f"PTB-XL showcase entry not found for {key[0]} ecg_id={key[1]}"
            ) from error

    def _key_from_waveform(self, waveform_bytes: bytes) -> tuple[str, int]:
        try:
            value = json.loads(waveform_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("canonical waveform JSON is malformed") from error
        if not isinstance(value, dict):
            raise ValueError("canonical waveform JSON must be an object")
        warnings = value.get("parser_warnings", [])
        if not isinstance(warnings, list):
            raise ValueError("PTB-XL showcase metadata is missing")
        for item in warnings:
            match = re.search(r"metadata:\s*([A-Z]+),\s*ecg_id=(\d+)", str(item))
            if match:
                label = match.group(1)
                if label not in LABEL_ORDER:
                    raise ValueError("PTB-XL showcase label is outside the fixed label mapping")
                return label, int(match.group(2))
        reference = str(value.get("study_reference", ""))
        reference_match = re.search(
            r"\b(NORM|MI|STTC|CD|HYP)-0*(\d+)(?:\b|$)",
            reference,
        )
        if reference_match:
            return reference_match.group(1), int(reference_match.group(2))
        raise ValueError("PTB-XL representative label metadata is missing")

    def _load_manifest(self) -> dict[str, Any]:
        if self._manifest is None:
            if not self._manifest_path.is_file():
                raise FileNotFoundError(f"showcase manifest not found: {self._manifest_path}")
            value = json.loads(self._manifest_path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("showcase manifest must be an object")
            if tuple(value.get("label_order", ())) != LABEL_ORDER:
                raise ValueError("showcase manifest label order is incompatible")
            if value.get("provider_name") != PROVIDER_NAME:
                raise ValueError("showcase manifest provider name is incompatible")
            self._manifest = value
        return self._manifest

    def _load_entries(self) -> dict[tuple[str, int], _ShowcaseEntry]:
        if self._entries is None:
            manifest = self._load_manifest()
            entries: dict[tuple[str, int], _ShowcaseEntry] = {}
            raw_entries = manifest.get("entries")
            if not isinstance(raw_entries, list) or not raw_entries:
                raise ValueError("showcase manifest has no entries")
            for raw in raw_entries:
                if not isinstance(raw, dict):
                    raise ValueError("showcase manifest entry is malformed")
                entry = _entry_from_manifest(raw, manifest, self._artifact_root)
                entries[(entry.label, entry.ecg_id)] = entry
            self._entries = entries
        return self._entries


def _entry_from_manifest(
    raw: dict[str, Any], manifest: dict[str, Any], artifact_root: Path
) -> _ShowcaseEntry:
    label = str(raw["label"])
    ecg_id = int(raw["ecg_id"])
    image_path = _safe_artifact_path(artifact_root, str(raw["explanation_image"]))
    return _ShowcaseEntry(
        label,
        ecg_id,
        str(raw.get("model_name", manifest["model_name"])),
        str(raw.get("model_version", manifest["model_version"])),
        str(manifest["checkpoint_sha256"]),
        str(manifest["preprocessing_version"]),
        str(manifest["threshold_source"]),
        _float_mapping(raw["label_scores"]),
        _float_mapping(raw["thresholds"]),
        tuple(str(item) for item in raw.get("predicted_findings", ())),
        str(raw["explanation_label"]),
        image_path,
        tuple(str(item) for item in raw.get("warnings", ())),
        {str(key): str(value) for key, value in raw.get("provenance", {}).items()},
    )


def _safe_artifact_path(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    if root not in (path, *path.parents):
        raise ValueError("showcase artifact path escapes the artifact root")
    return path


def _float_mapping(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ValueError("showcase score mapping is malformed")
    return {str(key): float(value[key]) for key in LABEL_ORDER}


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        cleaned = _safe_text(value)
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return tuple(result)


def _safe_text(value: str, limit: int = 240) -> str:
    compact = " ".join(value.split())
    return compact[:limit]
