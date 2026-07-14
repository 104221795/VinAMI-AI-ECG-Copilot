"""Storage boundary for ECG source, waveform, preview, and explanation artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ArtifactMetadata:
    artifact_id: UUID
    artifact_kind: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    state: str
    created_at: datetime
    original_filename: str | None = None


class ECGArtifactStore(Protocol):
    """Persist bytes without exposing implementation paths to callers."""

    def write(
        self,
        content: bytes,
        *,
        artifact_kind: str,
        content_type: str,
        original_filename: str | None = None,
    ) -> ArtifactMetadata: ...

    def open(self, artifact_id: UUID) -> BinaryIO: ...
    def verify(self, artifact_id: UUID, expected_checksum: str) -> bool: ...
