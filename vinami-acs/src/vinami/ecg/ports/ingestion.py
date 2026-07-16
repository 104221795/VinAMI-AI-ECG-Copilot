"""Replaceable ECG source and parser contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ParsedWaveform:
    study_reference: str
    lead_names: tuple[str, ...]
    samples: tuple[tuple[float, ...], ...]
    sampling_rate_hz: float
    amplitude_unit: str
    acquisition_at: datetime
    source_format: str
    source_device: str | None
    calibration: str | None
    parser_name: str
    parser_version: str
    parser_warnings: tuple[str, ...] = ()
    source_identifiers: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    study_reference: str
    source_format: str
    parser_name: str
    parser_version: str
    acquisition_at: datetime
    parser_warnings: tuple[str, ...] = ()


ParsedECG = ParsedWaveform | ParsedDocument


@dataclass(frozen=True, slots=True)
class SourceInfo:
    connector_id: str
    display_name: str
    source_type: str
    available: bool
    capabilities: tuple[str, ...]
    detail: str
    connector_type: str = "local_adapter"
    profile: str | None = None
    version: str | None = None


class ECGSourceAdapter(Protocol):
    source_type: str

    def validate_source(self, content: bytes, content_type: str) -> None: ...
    def parse(
        self, content: bytes, *, study_reference: str, acquisition_at: datetime
    ) -> ParsedECG: ...
    def create_preview(self, content: bytes, parsed: ParsedECG) -> tuple[bytes, str] | None: ...
    def get_source_info(self) -> SourceInfo: ...
    def health(self) -> SourceInfo: ...


class ECGSourceConnector(Protocol):
    connector_id: str

    def query(self, external_reference: str) -> tuple[str, ...]: ...
    def retrieve(self, external_reference: str, attempt: int = 0) -> bytes: ...
    def receive(self, content: bytes) -> str: ...
    def health(self) -> SourceInfo: ...


DICOMSourceConnector = ECGSourceConnector
