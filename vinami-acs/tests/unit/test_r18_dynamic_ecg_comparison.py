"""R18 dynamic ECG comparison tests for technical signal-change assistance."""

from __future__ import annotations

from math import exp

from vinami.ecg.application.service import (
    _compare_leads,
    _signal_feature_deltas,
    _technical_change_indicators,
)
from vinami.ecg.domain.clinical import STANDARD_12_LEADS


def test_r18_detects_st_t_proxy_change_without_clinical_conclusion() -> None:
    baseline = _waveform()
    current = _waveform(st_offset_uv=160.0, t_wave_scale=3.0)

    deltas, rhythm, st_t = _signal_feature_deltas(baseline, current, 100.0, 100.0)

    by_name = {item.feature_name: item for item in deltas}
    assert by_name["st_level_proxy_uv"].status == "changed"
    assert st_t
    assert "diagnosis" not in " ".join(st_t).lower()


def test_r18_indicators_require_physician_review_and_stay_technical() -> None:
    baseline = _waveform()
    current = _waveform(st_offset_uv=140.0)
    lead_values = _compare_leads(baseline, current)
    _, rhythm, st_t = _signal_feature_deltas(baseline, current, 100.0, 100.0)

    indicators = _technical_change_indicators(
        lead_values,
        (),
        rhythm,
        st_t,
        (),
        "analysis_unavailable",
    )

    assert "physician review required before clinical use" in indicators
    assert any("technical" in item or "proxy" in item for item in indicators)
    assert "clinical deterioration" not in " ".join(indicators).lower()


def _waveform(
    *,
    st_offset_uv: float = 0.0,
    t_wave_scale: float = 1.0,
    sampling_rate: int = 100,
) -> dict[str, tuple[float, ...]]:
    samples_per_lead = sampling_rate * 10
    peaks = tuple(range(50, samples_per_lead - 50, sampling_rate))
    output: dict[str, tuple[float, ...]] = {}
    for lead_index, lead_name in enumerate(STANDARD_12_LEADS):
        values: list[float] = []
        scale = 1.0 - (lead_index * 0.015)
        for index in range(samples_per_lead):
            value = 15.0
            for peak in peaks:
                qrs = 900.0 * exp(-((index - peak) / 2.5) ** 2)
                t_wave = 85.0 * t_wave_scale * exp(-((index - (peak + 25)) / 7.0) ** 2)
                st_segment = st_offset_uv if peak + 8 <= index <= peak + 16 else 0.0
                value += (qrs + t_wave + st_segment) * scale
            values.append(round(value, 4))
        output[lead_name] = tuple(values)
    return output
