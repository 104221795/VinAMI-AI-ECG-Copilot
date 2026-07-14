"""Deterministic canonical waveform preprocessing and technical quality assessment."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256

from vinami.ecg.domain.clinical import (
    STANDARD_12_LEADS,
    ECGQualityResult,
    ECGWaveform,
    TechnicalQualityStatus,
)
from vinami.ecg.ports.ingestion import ParsedWaveform
from vinami.ecg.ports.preprocessing import PreprocessingResult


class CanonicalECGPreprocessor:
    version = "canonical-normalization-1.0.0"

    def normalize(self, value: ParsedWaveform) -> PreprocessingResult:
        unit = value.amplitude_unit.strip()
        factor, normalized_unit, conversion = _unit_conversion(unit)
        normalized_samples = tuple(
            tuple(round(sample * factor, 6) for sample in lead) for lead in value.samples
        )
        document = {
            "schema_version": "1.0",
            "study_reference": value.study_reference,
            "sampling_rate_hz": value.sampling_rate_hz,
            "amplitude_unit": normalized_unit,
            "source_amplitude_unit": unit,
            "conversion_method": conversion,
            "preprocessing_version": self.version,
            "lead_order": list(value.lead_names),
            "leads": [
                {"name": name, "samples": list(samples)}
                for name, samples in zip(value.lead_names, normalized_samples, strict=True)
            ],
        }
        content = json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
        sample_count = len(normalized_samples[0])
        waveform = ECGWaveform(
            study_reference=value.study_reference,
            lead_names=value.lead_names,
            samples_per_lead=sample_count,
            sampling_rate_hz=value.sampling_rate_hz,
            duration_seconds=sample_count / value.sampling_rate_hz,
            original_amplitude_unit=unit,
            normalized_amplitude_unit=normalized_unit,
            time_unit="second",
            acquisition_at=value.acquisition_at,
            source_format=value.source_format,
            source_device=value.source_device,
            missing_leads=tuple(lead for lead in STANDARD_12_LEADS if lead not in value.lead_names),
            parser_warnings=value.parser_warnings,
            preprocessing_version=self.version,
            checksum=sha256(content).hexdigest(),
            conversion_method=conversion,
            conversion_version="ucum-demo-1" if conversion else None,
            calibration=value.calibration,
        )
        return PreprocessingResult(
            waveform, content, None, None, (conversion,) if conversion else (), ()
        )


class TechnicalECGQualityEngine:
    version = "technical-quality-1.0.0"

    def assess(self, value: ParsedWaveform, preprocessing: PreprocessingResult) -> ECGQualityResult:
        reasons: list[str] = []
        affected: list[str] = []
        if preprocessing.waveform.missing_leads:
            reasons.append("missing_standard_leads")
            affected.extend(preprocessing.waveform.missing_leads)
        for lead_name, samples in zip(value.lead_names, value.samples, strict=True):
            spread = max(samples) - min(samples)
            flat_fraction = sum(1 for item in samples if abs(item - samples[0]) < 1e-9) / len(
                samples
            )
            if spread < 1e-6 or flat_fraction > 0.95:
                reasons.append("flat_line_segment")
                affected.append(lead_name)
        if len(affected) >= max(2, len(value.lead_names) // 3):
            status = TechnicalQualityStatus.POOR
        elif reasons:
            status = TechnicalQualityStatus.LIMITED
        else:
            status = TechnicalQualityStatus.ACCEPTABLE
        return ECGQualityResult(
            status,
            tuple(sorted(set(reasons))),
            tuple(sorted(set(affected))),
            value.parser_warnings,
            preprocessing.warnings,
            self.version,
            datetime.now(UTC),
        )


def _unit_conversion(unit: str) -> tuple[float, str, str | None]:
    normalized = unit.lower().replace("µ", "u")
    if normalized in {"uv", "microvolt", "microvolts"}:
        return 1.0, "uV", None
    if normalized in {"mv", "millivolt", "millivolts"}:
        return 1000.0, "uV", "mV_to_uV_x1000"
    raise ValueError("unsupported ECG amplitude unit")
