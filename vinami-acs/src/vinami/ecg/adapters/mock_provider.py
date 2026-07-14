"""Deterministic, non-clinical ECG AI demonstration provider."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from vinami.ecg.ports.provider import (
    AIProviderHealth,
    ECGExplanationRequest,
    ECGExplanationResult,
    ECGPredictionRequest,
    ECGPredictionResult,
    InputValidationResult,
    ModelInfo,
)


class MockECGAIProvider:
    def __init__(self, seed: str = "vinami-demo") -> None:
        self._seed = seed

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            "vinami-deterministic-ecg-fixture",
            "r3-demo-1",
            "deterministic-mock",
            "canonical waveform or derived fixture input",
            synthetic=True,
            label_order=("NORM", "MI", "STTC", "CD", "HYP"),
            threshold_source="synthetic demonstration thresholds",
        )

    def health(self) -> AIProviderHealth:
        return AIProviderHealth(True, "deterministic-mock", "synthetic research-use fixture")

    def validate_input(self, request: ECGPredictionRequest) -> InputValidationResult:
        if not request.input_reference.strip():
            return InputValidationResult(False, failure_reason="input reference is missing")
        if request.input_quality in {"poor", "insufficient", "unsupported", "failed"}:
            return InputValidationResult(
                False,
                ("Technical quality blocks normal model-score presentation.",),
                "input quality is not suitable for analysis",
            )
        return InputValidationResult(True)

    def predict(self, request: ECGPredictionRequest) -> ECGPredictionResult:
        started = datetime.now(UTC)
        if "provider-failure" in request.input_reference:
            raise RuntimeError("deterministic provider failure")
        if "provider-timeout" in request.input_reference:
            raise TimeoutError("deterministic provider timeout")
        validation = self.validate_input(request)
        if not validation.valid:
            completed = datetime.now(UTC)
            return ECGPredictionResult(
                request.study_id,
                "vinami-deterministic-ecg-fixture",
                "r3-demo-1",
                "deterministic-mock",
                started,
                completed,
                request.input_quality,
                {},
                {},
                (),
                (),
                validation.warnings,
                {"fixture_seed": self._seed, "synthetic": "true"},
                validation.failure_reason,
                True,
            )
        digest = sha256(
            f"{self._seed}:{request.study_id}:{request.input_reference}".encode()
        ).digest()
        labels = ("NORM", "MI", "STTC", "CD", "HYP")
        scores = {
            label: round(0.05 + digest[index] / 255 * 0.75, 4) for index, label in enumerate(labels)
        }
        thresholds = {label: 0.5 for label in labels}
        findings = tuple(
            ("MI-related ECG pattern" if label == "MI" else label)
            for label in labels
            if scores[label] >= thresholds[label]
        )
        completed = datetime.now(UTC)
        return ECGPredictionResult(
            request.study_id,
            "vinami-deterministic-ecg-fixture",
            "r3-demo-1",
            "deterministic-mock",
            started,
            completed,
            "acceptable",
            scores,
            thresholds,
            findings,
            (f"demo://heatmap/{request.study_id}",),
            ("Model-attention aid; not causal clinical evidence.",),
            {"fixture_seed": self._seed, "synthetic": "true"},
            None,
            True,
        )

    def explain(self, request: ECGExplanationRequest) -> ECGExplanationResult:
        svg = _synthetic_explanation(request.target_label)
        return ECGExplanationResult(
            request.study_id,
            request.target_label,
            f"demo://heatmap/{request.study_id}/{request.target_label}",
            "Model-attention aid; not causal clinical evidence.",
            svg,
            "image/svg+xml",
            True,
        )


def _synthetic_explanation(label: str) -> bytes:
    """Return a deterministic, visibly synthetic model-visualization fixture."""
    safe_label = "".join(
        character for character in label if character.isalnum() or character in " -_"
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="300" '
        'viewBox="0 0 900 300" role="img">'
        '<rect width="900" height="300" fill="#f3f6f7"/>'
        '<g fill="none" stroke="#007d75" stroke-width="8" opacity=".8">'
        '<path d="M20 170 L150 170 L190 130 L230 220 L270 70 L320 180 L450 180"/>'
        '<path d="M450 180 L570 180 L610 145 L650 210 L690 100 L730 180 L880 180"/>'
        '</g><ellipse cx="470" cy="160" rx="150" ry="90" fill="#d49b27" opacity=".28"/>'
        '<text x="30" y="42" font-family="Arial" font-size="22" fill="#14262b">'
        f"Synthetic model visualization: {safe_label}</text>"
        '<text x="30" y="275" font-family="Arial" font-size="18" fill="#52666b">'
        "Not a clinical localization claim</text>"
        "</svg>"
    ).encode()
