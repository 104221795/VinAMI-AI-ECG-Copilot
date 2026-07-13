"""Provider-neutral ECG AI port; no model framework belongs above this boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ECGPredictionRequest:
    study_id: UUID
    input_reference: str
    image_bytes: bytes | None = None


@dataclass(frozen=True, slots=True)
class ECGExplanationRequest:
    study_id: UUID
    input_reference: str
    target_label: str


@dataclass(frozen=True, slots=True)
class ModelInfo:
    name: str
    version: str
    provider_name: str
    input_contract: str


@dataclass(frozen=True, slots=True)
class AIProviderHealth:
    healthy: bool
    provider_name: str
    detail: str


@dataclass(frozen=True, slots=True)
class ECGPredictionResult:
    study_id: UUID
    model_name: str
    model_version: str
    provider_name: str
    started_at: datetime
    completed_at: datetime
    input_quality: str
    label_scores: dict[str, float]
    thresholds: dict[str, float]
    predicted_findings: tuple[str, ...]
    explanation_references: tuple[str, ...]
    warnings: tuple[str, ...]
    provenance: dict[str, str]
    failure_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ECGExplanationResult:
    study_id: UUID
    target_label: str
    reference: str
    warning: str


class ECGAIProvider(Protocol):
    def predict(self, request: ECGPredictionRequest) -> ECGPredictionResult: ...
    def explain(self, request: ECGExplanationRequest) -> ECGExplanationResult: ...
    def health(self) -> AIProviderHealth: ...
    def get_model_info(self) -> ModelInfo: ...
