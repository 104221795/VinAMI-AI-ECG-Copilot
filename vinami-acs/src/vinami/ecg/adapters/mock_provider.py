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
    ModelInfo,
)


class MockECGAIProvider:
    def __init__(self, seed: str = "vinami-demo") -> None:
        self._seed = seed

    def get_model_info(self) -> ModelInfo:
        return ModelInfo("mock-convnextv2", "demo-1", "mock", "CWT image")

    def health(self) -> AIProviderHealth:
        return AIProviderHealth(True, "mock", "deterministic demonstration provider")

    def predict(self, request: ECGPredictionRequest) -> ECGPredictionResult:
        started = datetime.now(UTC)
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
            "mock-convnextv2",
            "demo-1",
            "mock",
            started,
            completed,
            "acceptable",
            scores,
            thresholds,
            findings,
            (f"demo://heatmap/{request.study_id}",),
            ("Model-attention aid; not causal clinical evidence.",),
            {"seed": self._seed},
            None,
        )

    def explain(self, request: ECGExplanationRequest) -> ECGExplanationResult:
        return ECGExplanationResult(
            request.study_id,
            request.target_label,
            f"demo://heatmap/{request.study_id}/{request.target_label}",
            "Model-attention aid; not causal clinical evidence.",
        )
