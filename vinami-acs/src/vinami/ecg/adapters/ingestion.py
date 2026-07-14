"""Standards-shaped local ECG source adapters for R3."""

from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO
from math import pi, sin
from typing import Any
from xml.etree.ElementTree import Element

from vinami.ecg.domain.clinical import STANDARD_12_LEADS
from vinami.ecg.ports.ingestion import ParsedDocument, ParsedECG, ParsedWaveform, SourceInfo


class UnsupportedECGSourceError(ValueError):
    """Raised when bytes are valid but not a supported ECG profile."""


class CanonicalWaveformAdapter:
    source_type = "canonical_waveform"
    parser_name = "vinami-canonical-json"
    parser_version = "1.0.0"

    def validate_source(self, content: bytes, content_type: str) -> None:
        if content_type.split(";", 1)[0].lower() not in {
            "application/json",
            "application/vnd.vinami.ecg+json",
        }:
            raise UnsupportedECGSourceError(
                "canonical waveform requires the VinAMI JSON media type"
            )

    def parse(
        self, content: bytes, *, study_reference: str, acquisition_at: datetime
    ) -> ParsedWaveform:
        try:
            value = json.loads(content)
            leads = tuple(str(item["name"]) for item in value["leads"])
            samples = tuple(
                tuple(float(sample) for sample in item["samples"]) for item in value["leads"]
            )
            sampling_rate = float(value["sampling_rate_hz"])
            unit = str(value["amplitude_unit"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise UnsupportedECGSourceError("canonical waveform contract is malformed") from error
        _validate_waveform(leads, samples, sampling_rate)
        return ParsedWaveform(
            study_reference=study_reference,
            lead_names=leads,
            samples=samples,
            sampling_rate_hz=sampling_rate,
            amplitude_unit=unit,
            acquisition_at=acquisition_at,
            source_format="vinami-canonical-json-v1",
            source_device=_optional_text(value.get("source_device")),
            calibration=_optional_text(value.get("calibration")),
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            parser_warnings=tuple(str(item) for item in value.get("parser_warnings", [])),
        )

    def create_preview(self, content: bytes, parsed: ParsedECG) -> tuple[bytes, str] | None:
        if isinstance(parsed, ParsedDocument):
            return None
        return _waveform_preview(parsed), "image/svg+xml"

    def get_source_info(self) -> SourceInfo:
        return SourceInfo(
            "canonical-json",
            "VinAMI canonical waveform",
            self.source_type,
            True,
            ("receive", "parse", "waveform"),
            "Local deterministic adapter",
        )

    def health(self) -> SourceInfo:
        return self.get_source_info()


class CanonicalXMLAdapter:
    source_type = "vendor_xml"
    parser_name = "vinami-canonical-xml"
    parser_version = "1.0.0"
    namespace = "urn:vinami:ecg:canonical:1"

    def validate_source(self, content: bytes, content_type: str) -> None:
        if content_type.split(";", 1)[0].lower() not in {"application/xml", "text/xml"}:
            raise UnsupportedECGSourceError("XML ECG requires an XML media type")
        prefix = content[:4096].upper()
        if b"<!DOCTYPE" in prefix or b"<!ENTITY" in prefix:
            raise UnsupportedECGSourceError("XML external entities are prohibited")

    def parse(
        self, content: bytes, *, study_reference: str, acquisition_at: datetime
    ) -> ParsedWaveform:
        try:
            from defusedxml import ElementTree

            root = ElementTree.fromstring(content)
        except Exception as error:
            raise UnsupportedECGSourceError("XML ECG could not be parsed safely") from error
        if root.tag != f"{{{self.namespace}}}ECGWaveform":
            raise UnsupportedECGSourceError("unsupported XML ECG profile")
        return self._waveform(root, study_reference, acquisition_at)

    def _waveform(
        self, root: Element, study_reference: str, acquisition_at: datetime
    ) -> ParsedWaveform:
        ns = {"v": self.namespace}
        rate_node = root.find("v:SamplingRate", ns)
        unit_node = root.find("v:AmplitudeUnit", ns)
        if (
            rate_node is None
            or unit_node is None
            or rate_node.text is None
            or unit_node.text is None
        ):
            raise UnsupportedECGSourceError("XML ECG sampling metadata is missing")
        leads: list[str] = []
        samples: list[tuple[float, ...]] = []
        for node in root.findall("v:Lead", ns):
            name = node.attrib.get("name")
            if not name or node.text is None:
                raise UnsupportedECGSourceError("XML ECG lead is incomplete")
            leads.append(name)
            try:
                samples.append(tuple(float(item) for item in node.text.split()))
            except ValueError as error:
                raise UnsupportedECGSourceError("XML ECG samples are malformed") from error
        rate = float(rate_node.text)
        _validate_waveform(tuple(leads), tuple(samples), rate)
        return ParsedWaveform(
            study_reference,
            tuple(leads),
            tuple(samples),
            rate,
            unit_node.text,
            acquisition_at,
            "vinami-canonical-xml-v1",
            root.attrib.get("device"),
            root.attrib.get("calibration"),
            self.parser_name,
            self.parser_version,
        )

    def create_preview(self, content: bytes, parsed: ParsedECG) -> tuple[bytes, str] | None:
        return (
            (_waveform_preview(parsed), "image/svg+xml")
            if isinstance(parsed, ParsedWaveform)
            else None
        )

    def get_source_info(self) -> SourceInfo:
        return SourceInfo(
            "canonical-xml",
            "VinAMI canonical XML profile",
            self.source_type,
            True,
            ("receive", "parse", "waveform"),
            "Only urn:vinami:ecg:canonical:1 is supported",
        )

    def health(self) -> SourceInfo:
        return self.get_source_info()


class PDFECGAdapter:
    source_type = "pdf_document"
    parser_name = "pdf-document"
    parser_version = "1.0.0"

    def validate_source(self, content: bytes, content_type: str) -> None:
        if content_type.split(";", 1)[0].lower() != "application/pdf" or not content.startswith(
            b"%PDF-"
        ):
            raise UnsupportedECGSourceError("ECG document is not a valid PDF file")

    def parse(
        self, content: bytes, *, study_reference: str, acquisition_at: datetime
    ) -> ParsedDocument:
        return ParsedDocument(
            study_reference,
            "pdf-document",
            self.parser_name,
            self.parser_version,
            acquisition_at,
            ("Structured waveform unavailable; automated waveform analysis is unavailable.",),
        )

    def create_preview(self, content: bytes, parsed: ParsedECG) -> tuple[bytes, str] | None:
        return content, "application/pdf"

    def get_source_info(self) -> SourceInfo:
        return SourceInfo(
            "pdf-document",
            "ECG PDF document",
            self.source_type,
            True,
            ("receive", "preview", "physician-review"),
            "View-only; no waveform extraction",
        )

    def health(self) -> SourceInfo:
        return self.get_source_info()


class DICOMWaveformAdapter:
    source_type = "dicom_file"
    parser_name = "pydicom-waveform"
    parser_version = "1.0.0"

    def validate_source(self, content: bytes, content_type: str) -> None:
        if (
            content_type.split(";", 1)[0].lower() != "application/dicom"
            or len(content) < 132
            or content[128:132] != b"DICM"
        ):
            raise UnsupportedECGSourceError("DICOM ECG requires a Part 10 DICOM file")

    def parse(
        self, content: bytes, *, study_reference: str, acquisition_at: datetime
    ) -> ParsedWaveform:
        try:
            from pydicom import dcmread, waveforms

            dataset = dcmread(BytesIO(content), force=False)
            sequences = getattr(dataset, "WaveformSequence", None)
            if not sequences:
                raise UnsupportedECGSourceError("DICOM object has no waveform sequence")
            group = sequences[0]
            multiplex_array = waveforms.multiplex_array  # type: ignore[attr-defined]
            array = multiplex_array(dataset, 0, as_raw=False)
        except UnsupportedECGSourceError:
            raise
        except Exception as error:
            raise UnsupportedECGSourceError("DICOM waveform could not be decoded") from error
        channels = list(getattr(group, "ChannelDefinitionSequence", []))
        lead_names = tuple(_dicom_lead_name(item, index) for index, item in enumerate(channels))
        samples = tuple(
            tuple(float(value) for value in array[:, index]) for index in range(array.shape[1])
        )
        rate = float(group.SamplingFrequency)
        _validate_waveform(lead_names, samples, rate)
        identifiers = tuple(
            (name, str(getattr(dataset, name, "")))
            for name in ("StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID")
            if getattr(dataset, name, None)
        )
        return ParsedWaveform(
            study_reference,
            lead_names,
            samples,
            rate,
            "uV",
            acquisition_at,
            "dicom-waveform",
            str(getattr(dataset, "ManufacturerModelName", "")) or None,
            None,
            self.parser_name,
            self.parser_version,
            (),
            identifiers,
        )

    def create_preview(self, content: bytes, parsed: ParsedECG) -> tuple[bytes, str] | None:
        return (
            (_waveform_preview(parsed), "image/svg+xml")
            if isinstance(parsed, ParsedWaveform)
            else None
        )

    def get_source_info(self) -> SourceInfo:
        return SourceInfo(
            "local-dicom",
            "Local DICOM ECG",
            self.source_type,
            True,
            ("receive", "parse", "waveform"),
            "Local Part 10 waveform ingestion through pydicom",
        )

    def health(self) -> SourceInfo:
        try:
            import pydicom  # noqa: F401
        except ImportError:
            return SourceInfo(
                "local-dicom",
                "Local DICOM ECG",
                self.source_type,
                False,
                (),
                "pydicom is unavailable",
            )
        return self.get_source_info()


class ECGSourceRegistry:
    def __init__(self, adapters: tuple[Any, ...]) -> None:
        self._adapters = {adapter.source_type: adapter for adapter in adapters}

    def select(self, source_type: str) -> Any:
        try:
            return self._adapters[source_type]
        except KeyError as error:
            raise UnsupportedECGSourceError("ECG source type is not configured") from error

    def source_info(self) -> tuple[SourceInfo, ...]:
        return tuple(adapter.health() for adapter in self._adapters.values())


class MockDICOMSourceConnector:
    """Deterministic connector fixture; it does not represent a live PACS connection."""

    def query(self, external_reference: str) -> tuple[str, ...]:
        return (external_reference,) if external_reference == "R3-DICOM-001" else ()

    def retrieve(self, external_reference: str) -> bytes:
        if external_reference != "R3-DICOM-001":
            raise FileNotFoundError("mock DICOM source reference is unavailable")
        return build_demo_dicom()

    def receive(self, content: bytes) -> str:
        DICOMWaveformAdapter().validate_source(content, "application/dicom")
        return "R3-DICOM-RECEIVED"

    def health(self) -> SourceInfo:
        return SourceInfo(
            "mock-dicom-source",
            "Deterministic mock DICOM source",
            "dicom_connector",
            True,
            ("query", "retrieve", "receive"),
            "Synthetic local connector; no live hospital system",
        )


def build_demo_waveform(
    *, poor_quality: bool = False, seconds: int = 5, sampling_rate: int = 100
) -> bytes:
    sample_count = seconds * sampling_rate
    leads = []
    for index, name in enumerate(STANDARD_12_LEADS):
        values = [
            0.0
            if poor_quality and name in {"V1", "V2"}
            else round(250 * sin(2 * pi * (1.0 + index * 0.01) * position / sampling_rate), 3)
            for position in range(sample_count)
        ]
        leads.append({"name": name, "samples": values})
    return json.dumps(
        {
            "schema_version": "1.0",
            "sampling_rate_hz": sampling_rate,
            "amplitude_unit": "uV",
            "source_device": "VinAMI deterministic fixture",
            "calibration": "10 mm/mV",
            "leads": leads,
        },
        separators=(",", ":"),
    ).encode()


def build_demo_xml() -> bytes:
    waveform = json.loads(build_demo_waveform(seconds=2))
    leads = "".join(
        f'<Lead name="{lead["name"]}">{" ".join(str(value) for value in lead["samples"])}</Lead>'
        for lead in waveform["leads"]
    )
    return (
        '<ECGWaveform xmlns="urn:vinami:ecg:canonical:1" '
        'device="VinAMI XML fixture" calibration="10 mm/mV">'
        "<SamplingRate>100</SamplingRate><AmplitudeUnit>uV</AmplitudeUnit>"
        f"{leads}</ECGWaveform>"
    ).encode()


def build_demo_dicom() -> bytes:
    try:
        import numpy as np
        from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
        from pydicom.sequence import Sequence
        from pydicom.uid import UID, ExplicitVRLittleEndian, generate_uid
    except ImportError as error:
        raise RuntimeError("pydicom and numpy are required for the DICOM fixture") from error
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = UID("1.2.840.10008.5.1.4.1.1.9.1.1")
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    dataset = FileDataset("", {}, file_meta=meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = meta.MediaStorageSOPClassUID
    dataset.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    dataset.StudyInstanceUID = generate_uid()
    dataset.SeriesInstanceUID = generate_uid()
    dataset.ManufacturerModelName = "VinAMI DICOM fixture"
    sample_count = 200
    matrix = np.array(
        [
            [int(1000 * sin(2 * pi * (1 + lead * 0.01) * point / 100)) for lead in range(12)]
            for point in range(sample_count)
        ],
        dtype=np.int16,
    )
    group = Dataset()
    group.NumberOfWaveformChannels = 12
    group.NumberOfWaveformSamples = sample_count
    group.SamplingFrequency = 100
    group.WaveformBitsAllocated = 16
    group.WaveformSampleInterpretation = "SS"
    group.WaveformData = matrix.tobytes()
    channels = []
    for name in STANDARD_12_LEADS:
        channel = Dataset()
        source = Dataset()
        source.CodeMeaning = name
        channel.ChannelSourceSequence = Sequence([source])
        channel.ChannelSensitivity = 1.0
        channel.ChannelBaseline = 0.0
        channel.ChannelSensitivityCorrectionFactor = 1.0
        channels.append(channel)
    group.ChannelDefinitionSequence = Sequence(channels)
    dataset.WaveformSequence = Sequence([group])
    stream = BytesIO()
    dataset.save_as(stream, enforce_file_format=True)
    return stream.getvalue()


def _dicom_lead_name(channel: Any, index: int) -> str:
    try:
        name = str(channel.ChannelSourceSequence[0].CodeMeaning)
    except (AttributeError, IndexError, TypeError):
        name = f"CHANNEL_{index + 1}"
    return name if name in STANDARD_12_LEADS else name


def _validate_waveform(
    leads: tuple[str, ...], samples: tuple[tuple[float, ...], ...], rate: float
) -> None:
    if not leads or len(leads) != len(samples) or len(set(leads)) != len(leads):
        raise UnsupportedECGSourceError("waveform lead structure is invalid")
    lengths = {len(values) for values in samples}
    if rate <= 0 or len(lengths) != 1 or not lengths or next(iter(lengths)) == 0:
        raise UnsupportedECGSourceError("waveform sample shape is invalid")


def _waveform_preview(parsed: ParsedWaveform) -> bytes:
    width, height = 900, 240
    values = parsed.samples[0]
    limit = min(len(values), 600)
    maximum = max(max(abs(item) for item in values[:limit]), 1.0)
    points = " ".join(
        f"{20 + index * (width - 40) / max(limit - 1, 1):.1f},"
        f"{height / 2 - values[index] / maximum * 80:.1f}"
        for index in range(limit)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="#fff"/>'
        f'<path d="M20 {height / 2} H{width - 20}" stroke="#d5dfe1"/>'
        f'<polyline points="{points}" fill="none" stroke="#14262b" stroke-width="1.2"/>'
        f'<text x="20" y="26" font-family="Arial" font-size="16">'
        f"Lead {parsed.lead_names[0]} technical preview</text></svg>"
    ).encode()


def _optional_text(value: object) -> str | None:
    return str(value) if value is not None and str(value).strip() else None
