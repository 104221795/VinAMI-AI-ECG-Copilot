"""Explicit provider selection with no implicit mock fallback."""

from vinami.ecg.adapters.mock_provider import MockECGAIProvider
from vinami.ecg.ports.provider import ECGAIProvider


class ProviderRegistry:
    def __init__(
        self, providers: dict[str, ECGAIProvider], allow_mock_fallback: bool = False
    ) -> None:
        self._providers = providers
        self._fallback = allow_mock_fallback

    def select(self, name: str) -> ECGAIProvider:
        if name in self._providers:
            return self._providers[name]
        if self._fallback:
            return self._providers.get("mock", MockECGAIProvider())
        raise ValueError(f"ECG AI provider {name} is not configured")
