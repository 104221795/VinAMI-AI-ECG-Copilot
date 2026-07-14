"""Versioned signal preprocessing and technical-quality ports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from vinami.ecg.domain.clinical import ECGQualityResult, ECGWaveform
from vinami.ecg.ports.ingestion import ParsedWaveform


@dataclass(frozen=True, slots=True)
class PreprocessingResult:
    waveform: ECGWaveform
    normalized_content: bytes
    model_input_content: bytes | None
    model_input_content_type: str | None
    transformations: tuple[str, ...]
    warnings: tuple[str, ...]


class ECGPreprocessor(Protocol):
    def normalize(self, value: ParsedWaveform) -> PreprocessingResult: ...


class ECGQualityEngine(Protocol):
    def assess(
        self, value: ParsedWaveform, preprocessing: PreprocessingResult
    ) -> ECGQualityResult: ...
