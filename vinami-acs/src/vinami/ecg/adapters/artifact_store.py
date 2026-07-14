"""Local development ECG artifact storage with integrity and content checks."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from io import BufferedReader
from pathlib import Path
from uuid import UUID, uuid4

from vinami.ecg.ports.artifacts import ArtifactMetadata


class ArtifactValidationError(ValueError):
    """Raised when untrusted artifact bytes violate the storage contract."""


class LocalECGArtifactStore:
    """Filesystem adapter using generated identifiers and no caller-controlled paths."""

    _ALLOWED = frozenset(
        {
            "application/vnd.vinami.ecg+json",
            "application/json",
            "application/dicom",
            "application/xml",
            "text/xml",
            "application/pdf",
            "image/svg+xml",
            "image/png",
        }
    )

    def __init__(self, root: Path, max_size_bytes: int = 25 * 1024 * 1024) -> None:
        self._root = root.resolve()
        self._max_size = max_size_bytes
        self._root.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        content: bytes,
        *,
        artifact_kind: str,
        content_type: str,
        original_filename: str | None = None,
    ) -> ArtifactMetadata:
        if not content:
            raise ArtifactValidationError("artifact is empty")
        if len(content) > self._max_size:
            raise ArtifactValidationError("artifact exceeds the configured size limit")
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type not in self._ALLOWED:
            raise ArtifactValidationError("artifact media type is not supported")
        _validate_signature(content, media_type)
        artifact_id = uuid4()
        target = self._path(artifact_id)
        target.write_bytes(content)
        return ArtifactMetadata(
            artifact_id=artifact_id,
            artifact_kind=artifact_kind,
            content_type=media_type,
            size_bytes=len(content),
            checksum_sha256=sha256(content).hexdigest(),
            state="accepted",
            created_at=datetime.now(UTC),
            original_filename=Path(original_filename).name if original_filename else None,
        )

    def open(self, artifact_id: UUID) -> BufferedReader:
        path = self._path(artifact_id)
        if not path.is_file():
            raise FileNotFoundError("ECG artifact is unavailable")
        return path.open("rb")

    def verify(self, artifact_id: UUID, expected_checksum: str) -> bool:
        try:
            with self.open(artifact_id) as stream:
                return sha256(stream.read()).hexdigest() == expected_checksum.lower()
        except FileNotFoundError:
            return False

    def _path(self, artifact_id: UUID) -> Path:
        path = (self._root / artifact_id.hex).resolve()
        if path.parent != self._root:
            raise ArtifactValidationError("invalid artifact identifier")
        return path


def _validate_signature(content: bytes, content_type: str) -> None:
    stripped = content.lstrip()
    if content_type == "application/pdf" and not content.startswith(b"%PDF-"):
        raise ArtifactValidationError("content does not have a PDF signature")
    if content_type == "application/dicom" and not (
        len(content) >= 132 and content[128:132] == b"DICM"
    ):
        raise ArtifactValidationError("content does not have a DICOM file signature")
    if content_type in {"application/xml", "text/xml"}:
        prefix = stripped[:2048].upper()
        if not stripped.startswith(b"<") or b"<!DOCTYPE" in prefix or b"<!ENTITY" in prefix:
            raise ArtifactValidationError("unsafe or malformed XML content")
    if content_type in {
        "application/json",
        "application/vnd.vinami.ecg+json",
    } and not stripped.startswith(b"{"):
        raise ArtifactValidationError("content does not have a JSON object signature")
    if content_type == "image/svg+xml" and not stripped.startswith(b"<svg"):
        raise ArtifactValidationError("content does not have an SVG signature")
