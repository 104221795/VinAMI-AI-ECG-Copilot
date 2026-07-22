"""R17 reconciliation classification for simulated hospital integration messages."""

from __future__ import annotations

from typing import Protocol

from vinami.integration.domain.model import IntegrationMessage


class IntegrationMessageLike(Protocol):
    """Read-only attributes required to classify an inbound message."""

    status: str
    message_type: str
    clinical_case_id: object | None
    validation_errors: tuple[str, ...]
    linked_record_ids: tuple[str, ...]
    retry_count: int
    dead_letter_reason: str | None


def classify_reconciliation(message: IntegrationMessage | IntegrationMessageLike) -> dict[str, object]:
    """Classify matching/review state without guessing identifiers or clinical values."""
    errors = tuple(message.validation_errors)
    lowered = " | ".join(errors).lower()
    if message.status == "processed" and message.linked_record_ids:
        if message.message_type == "lab_result_amendment":
            return _result(
                "amendment_matched",
                "Amendment matched to a previously processed internal record.",
                False,
            )
        return _result("matched", "Message matched to persisted internal evidence.", False)
    if message.status == "duplicate":
        return _result("duplicate", "Duplicate delivery was recognized by source message ID.", False)
    if message.clinical_case_id is None:
        return _result(
            "unmatched",
            "Message has no internal case identifier and requires manual review.",
            True,
        )
    if "predecessor" in lowered or "amendment" in lowered:
        return _result(
            "out_of_order",
            "Amendment predecessor is unavailable or has not been processed.",
            True,
        )
    if "unsupported unit" in lowered or "unsupported" in lowered:
        return _result(
            "unsupported",
            "Message contains unsupported schema, unit, or profile information.",
            True,
        )
    if message.status in {"failed", "dead_letter"}:
        return _result(
            "review_required",
            message.dead_letter_reason or "; ".join(errors) or "Processing failed.",
            True,
        )
    if message.status == "retry_pending":
        return _result(
            "retry_pending",
            "Temporary processing failure is awaiting retry.",
            False,
        )
    return _result(
        "pending",
        "Message is recorded but has not produced linked internal evidence yet.",
        False,
    )


def _result(status: str, reason: str, review_required: bool) -> dict[str, object]:
    return {
        "reconciliation_status": status,
        "reconciliation_reason": reason,
        "review_required": review_required,
    }
