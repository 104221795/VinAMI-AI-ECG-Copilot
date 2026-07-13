from uuid import uuid4

from vinami.ecg.adapters.mock_provider import MockECGAIProvider
from vinami.ecg.adapters.registry import ProviderRegistry
from vinami.ecg.ports.provider import ECGPredictionRequest


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
