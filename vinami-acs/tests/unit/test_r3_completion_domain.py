"""Focused R3 completion tests for hospital formats and technical workflow safety."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from vinami.ecg.adapters.ingestion import (
    DICOMWaveformAdapter,
    MockDICOMSourceConnector,
    UnsupportedECGSourceError,
    build_demo_dicom,
)
from vinami.ecg.domain.clinical import (
    ECGRepeatReminder,
    ReminderOrigin,
    ReminderStatus,
)
from vinami.shared.domain import DomainInvariantError
from vinami.shared.events.contracts import EventContext

NOW = datetime(2026, 7, 14, 10, 0, tzinfo=UTC)


def test_local_dicom_extracts_waveform_and_safe_technical_metadata() -> None:
    content = build_demo_dicom()
    adapter = DICOMWaveformAdapter()
    adapter.validate_source(content, "application/dicom")
    waveform = adapter.parse(content, study_reference="DICOM-LOCAL-001", acquisition_at=NOW)
    assert waveform.lead_names == (
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
    assert waveform.sampling_rate_hz == 100
    assert len(waveform.samples[0]) == 200
    assert waveform.calibration == "DICOM channel sensitivity applied by pydicom"
    assert {name for name, _ in waveform.source_identifiers} == {
        "StudyInstanceUID",
        "SeriesInstanceUID",
        "SOPInstanceUID",
    }


def test_dicom_rejects_malformed_and_non_waveform_objects() -> None:
    adapter = DICOMWaveformAdapter()
    with pytest.raises(UnsupportedECGSourceError):
        adapter.validate_source(b"not-dicom", "application/dicom")
    content = bytearray(build_demo_dicom())
    content[128:132] = b"FAIL"
    with pytest.raises(UnsupportedECGSourceError):
        adapter.validate_source(bytes(content), "application/dicom")


def test_mock_connector_has_deterministic_success_failure_timeout_and_retry() -> None:
    connector = MockDICOMSourceConnector()
    assert connector.health().connector_type == "deterministic_mock_dicom"
    assert connector.retrieve("R3-DICOM-001")[128:132] == b"DICM"
    with pytest.raises(ConnectionError):
        connector.retrieve("R3-DICOM-UNAVAILABLE")
    with pytest.raises(TimeoutError):
        connector.retrieve("R3-DICOM-TIMEOUT")
    with pytest.raises(TimeoutError):
        connector.retrieve("R3-DICOM-RETRY", attempt=0)
    assert connector.retrieve("R3-DICOM-RETRY", attempt=1)[128:132] == b"DICM"
    assert connector.retrieve("R3-DICOM-MALFORMED") == b"not-a-dicom-object"


def test_repeat_reminder_due_cancel_and_terminal_invariants() -> None:
    actor = uuid4()
    context = EventContext.start(actor)
    reminder = ECGRepeatReminder(
        id=uuid4(),
        clinical_case_id=uuid4(),
        source_study_id=uuid4(),
        requested_by=actor,
        requested_by_role="physician",
        reason="Physician requested repeat technical recording",
        due_at=NOW + timedelta(minutes=15),
        status=ReminderStatus.SCHEDULED,
        origin=ReminderOrigin.PHYSICIAN_REQUEST,
        created_at=NOW,
        updated_at=NOW,
        correlation_id=context.correlation_id,
    )
    assert reminder.effective_status(NOW) is ReminderStatus.SCHEDULED
    assert reminder.effective_status(reminder.due_at) is ReminderStatus.DUE
    assert (
        reminder.effective_status(reminder.due_at + timedelta(seconds=1)) is ReminderStatus.OVERDUE
    )
    reminder.cancel(actor, "No longer required after physician review", NOW, context)
    assert reminder.status is ReminderStatus.CANCELLED
    assert reminder.cancellation_reason is not None
    with pytest.raises(DomainInvariantError):
        reminder.complete(uuid4(), NOW, context)
