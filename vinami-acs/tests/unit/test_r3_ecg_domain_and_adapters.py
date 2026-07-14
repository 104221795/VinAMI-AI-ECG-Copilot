"""Focused R3 tests for source safety, quality, provider, and domain invariants."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from vinami.ecg.adapters.artifact_store import ArtifactValidationError, LocalECGArtifactStore
from vinami.ecg.adapters.ingestion import (
    CanonicalWaveformAdapter,
    CanonicalXMLAdapter,
    PDFECGAdapter,
    UnsupportedECGSourceError,
    build_demo_waveform,
    build_demo_xml,
)
from vinami.ecg.adapters.mock_provider import MockECGAIProvider
from vinami.ecg.adapters.preprocessing import CanonicalECGPreprocessor, TechnicalECGQualityEngine
from vinami.ecg.domain.clinical import ECGRepeatReminder, ReminderStatus
from vinami.ecg.ports.provider import ECGPredictionRequest
from vinami.shared.domain import DomainInvariantError
from vinami.shared.events.contracts import EventContext

NOW = datetime(2026, 7, 14, 8, 0, tzinfo=UTC)


def test_canonical_waveform_is_deterministic_and_quality_is_explicit() -> None:
    adapter = CanonicalWaveformAdapter()
    content = build_demo_waveform()
    adapter.validate_source(content, "application/vnd.vinami.ecg+json")
    parsed = adapter.parse(content, study_reference="R3-RAW-001", acquisition_at=NOW)
    normalized = CanonicalECGPreprocessor().normalize(parsed)
    quality = TechnicalECGQualityEngine().assess(parsed, normalized)
    assert normalized.waveform.lead_names == (
        "I",
        "II",
        "III",
        "aVR",
        "aVL",
        "aVF",
        "V1",
        "V2",
        "V3",
        "V4",
        "V5",
        "V6",
    )
    assert quality.status.value == "acceptable"
    assert (
        normalized.normalized_content
        == CanonicalECGPreprocessor().normalize(parsed).normalized_content
    )


def test_poor_quality_blocks_mock_score_presentation() -> None:
    request = ECGPredictionRequest(uuid4(), "artifact://poor", input_quality="poor")
    result = MockECGAIProvider().predict(request)
    assert result.failure_reason is not None
    assert result.label_scores == {}
    assert result.synthetic is True


def test_xml_profile_is_secure_and_narrow() -> None:
    adapter = CanonicalXMLAdapter()
    parsed = adapter.parse(build_demo_xml(), study_reference="R3-XML-001", acquisition_at=NOW)
    assert parsed.parser_name == "vinami-canonical-xml"
    unsafe = b'<!DOCTYPE x [<!ENTITY leak SYSTEM "file:///etc/passwd">]><x>&leak;</x>'
    with pytest.raises(UnsupportedECGSourceError):
        adapter.validate_source(unsafe, "application/xml")
    with pytest.raises(UnsupportedECGSourceError):
        adapter.parse(b"<Unknown/>", study_reference="bad", acquisition_at=NOW)


def test_pdf_is_view_only_and_does_not_create_waveform() -> None:
    adapter = PDFECGAdapter()
    content = b"%PDF-1.4\n%%EOF"
    adapter.validate_source(content, "application/pdf")
    parsed = adapter.parse(content, study_reference="R3-PDF-001", acquisition_at=NOW)
    assert parsed.source_format == "pdf-document"
    assert "waveform unavailable" in parsed.parser_warnings[0].lower()


def test_artifact_store_checks_signature_size_and_integrity(tmp_path: Path) -> None:
    store = LocalECGArtifactStore(tmp_path, max_size_bytes=1000)
    metadata = store.write(
        b"%PDF-1.4\n%%EOF",
        artifact_kind="raw_source",
        content_type="application/pdf",
        original_filename="../../ecg.pdf",
    )
    assert metadata.original_filename == "ecg.pdf"
    assert store.verify(metadata.artifact_id, metadata.checksum_sha256)
    with pytest.raises(ArtifactValidationError):
        store.write(b"not-pdf", artifact_kind="raw_source", content_type="application/pdf")


def test_repeat_reminder_transitions_are_versioned_and_idempotent() -> None:
    actor = uuid4()
    context = EventContext.start(actor)
    reminder = ECGRepeatReminder(
        uuid4(),
        uuid4(),
        uuid4(),
        actor,
        "Poor technical quality",
        NOW + timedelta(minutes=30),
        ReminderStatus.SCHEDULED,
        NOW,
        context.correlation_id,
    )
    reminder.acknowledge(actor, NOW + timedelta(minutes=1), context)
    assert reminder.status is ReminderStatus.ACKNOWLEDGED and reminder.record_version == 2
    study_id = uuid4()
    reminder.complete(study_id, NOW + timedelta(minutes=10), context)
    reminder.complete(study_id, NOW + timedelta(minutes=11), context)
    assert reminder.status is ReminderStatus.COMPLETED and reminder.record_version == 3
    with pytest.raises(DomainInvariantError):
        reminder.complete(uuid4(), NOW + timedelta(minutes=12), context)
