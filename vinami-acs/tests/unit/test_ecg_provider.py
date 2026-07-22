import json
from pathlib import Path
from uuid import uuid4

from vinami.ecg.adapters.ingestion import build_demo_waveform
from vinami.ecg.adapters.mock_provider import MockECGAIProvider
from vinami.ecg.adapters.precomputed_showcase_provider import (
    PROVIDER_NAME,
    PTBXLShowcaseProvider,
)
from vinami.ecg.adapters.registry import ProviderRegistry
from vinami.ecg.adapters.torch_provider import TorchConvNeXtV2Provider
from vinami.ecg.ports.provider import ECGExplanationRequest, ECGPredictionRequest


def test_mock_is_deterministic_and_safe() -> None:
    request = ECGPredictionRequest(uuid4(), "evidence://cwt")
    provider = MockECGAIProvider()
    first = provider.predict(request)
    second = provider.predict(request)
    assert first.label_scores == second.label_scores and "AMI" not in " ".join(
        first.predicted_findings
    )


def test_no_implicit_fallback() -> None:
    try:
        ProviderRegistry({"mock": MockECGAIProvider()}).select("torch")
    except ValueError:
        return
    raise AssertionError("provider registry silently fell back to mock")


def test_torch_provider_accepts_canonical_ptbxl_contract() -> None:
    provider = TorchConvNeXtV2Provider(_missing_checkpoint(), "0" * 64)
    request = ECGPredictionRequest(
        uuid4(),
        "artifact://waveform",
        waveform_bytes=build_demo_waveform(seconds=10, sampling_rate=100),
        input_quality="acceptable",
    )
    assert provider.validate_input(request).valid


def test_torch_provider_rejects_missing_lead_before_inference() -> None:
    provider = TorchConvNeXtV2Provider(_missing_checkpoint(), "0" * 64)
    value = json.loads(build_demo_waveform(seconds=10, sampling_rate=100))
    value["leads"] = value["leads"][:-1]
    result = provider.validate_input(
        ECGPredictionRequest(
            uuid4(),
            "artifact://waveform",
            waveform_bytes=json.dumps(value).encode(),
            input_quality="acceptable",
        )
    )
    assert not result.valid
    assert result.failure_reason is not None
    assert "standard 12 leads" in result.failure_reason


def test_torch_provider_rejects_wrong_sampling_contract() -> None:
    provider = TorchConvNeXtV2Provider(_missing_checkpoint(), "0" * 64)
    request = ECGPredictionRequest(
        uuid4(),
        "artifact://waveform",
        waveform_bytes=build_demo_waveform(seconds=10, sampling_rate=500),
        input_quality="acceptable",
    )
    result = provider.validate_input(request)
    assert not result.valid
    assert result.failure_reason is not None
    assert "100 Hz" in result.failure_reason


def test_precomputed_ptbxl_showcase_provider_reads_manifest(tmp_path: Path) -> None:
    (tmp_path / "reports").mkdir()
    image = tmp_path / "reports" / "gradcam.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    manifest = tmp_path / "reports" / "r23a_showcase_predictions.json"
    manifest.write_text(
        json.dumps(
            {
                "provider_name": PROVIDER_NAME,
                "model_name": "convnextv2_base",
                "model_version": "checkpoint-epoch-9",
                "checkpoint_sha256": "a" * 64,
                "preprocessing_version": "ptbxl-cwt-grid-adapter-r23a-v1",
                "threshold_source": "fixture thresholds",
                "label_order": ["NORM", "MI", "STTC", "CD", "HYP"],
                "entries": [
                    {
                        "label": "MI",
                        "ecg_id": 8,
                        "label_scores": {
                            "NORM": 0.1,
                            "MI": 0.8,
                            "STTC": 0.2,
                            "CD": 0.3,
                            "HYP": 0.4,
                        },
                        "thresholds": {
                            "NORM": 0.5,
                            "MI": 0.5,
                            "STTC": 0.5,
                            "CD": 0.5,
                            "HYP": 0.5,
                        },
                        "predicted_findings": ["MI-related ECG pattern"],
                        "explanation_label": "MI",
                        "explanation_image": "reports/gradcam.png",
                        "warnings": ["fixture warning"],
                        "provenance": {"source_ecg_id": "8"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    waveform = json.loads(build_demo_waveform(seconds=10, sampling_rate=100))
    waveform["parser_warnings"] = ["PTB-XL representative label metadata: MI, ecg_id=8."]
    waveform_bytes = json.dumps(waveform).encode()
    provider = PTBXLShowcaseProvider(manifest, tmp_path)
    prediction = provider.predict(
        ECGPredictionRequest(uuid4(), "artifact://waveform", waveform_bytes=waveform_bytes)
    )
    explanation = provider.explain(
        ECGExplanationRequest(
            prediction.study_id,
            "analysis://fixture",
            "MI",
            waveform_bytes=waveform_bytes,
        )
    )
    assert prediction.provider_name == PROVIDER_NAME
    assert prediction.label_scores["MI"] == 0.8
    assert explanation.content == b"\x89PNG\r\n\x1a\nfixture"
    assert explanation.content_type == "image/png"
    waveform["parser_warnings"] = []
    waveform["study_reference"] = "PTBXL-R23A-BESTPT-MI-00008-MI-00008"
    reference_only = provider.predict(
        ECGPredictionRequest(
            uuid4(),
            "artifact://normalized-waveform",
            waveform_bytes=json.dumps(waveform).encode(),
        )
    )
    assert reference_only.label_scores["MI"] == 0.8


def _missing_checkpoint() -> Path:
    return Path("missing.pt")
