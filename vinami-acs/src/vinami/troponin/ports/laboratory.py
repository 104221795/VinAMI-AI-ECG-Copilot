"""Replaceable laboratory-result connector and parser ports."""

from __future__ import annotations

from typing import Protocol


class LaboratoryConnectorError(RuntimeError):
    category = "connector_failure"


class LaboratoryUnavailableError(LaboratoryConnectorError):
    category = "connector_unavailable"


class LaboratoryTimeoutError(LaboratoryConnectorError):
    category = "connector_timeout"


class LaboratoryPayloadError(LaboratoryConnectorError):
    category = "malformed_payload"


class LaboratoryResultConnector(Protocol):
    connector_id: str
    connector_type: str

    def capabilities(self) -> tuple[str, ...]: ...
    def health(self) -> dict[str, object]: ...
    def fetch_result(self, reference: str) -> dict[str, object]: ...
    def parse_result(self, payload: dict[str, object]) -> dict[str, object]: ...
    def source_info(self) -> dict[str, str]: ...
