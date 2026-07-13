"""Load and validate the checked-in VinAMI demonstration workflow definition."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from vinami.shared.domain import DomainInvariantError
from vinami.workflow.domain.definition import Transition, WorkflowDefinition, WorkflowState


def load_demo_workflow_definition() -> WorkflowDefinition:
    """Load the versioned JSON definition packaged with this modular-monolith MVP."""
    content = (
        files("vinami.workflow.definitions")
        .joinpath("acs_demo_workflow_v1.json")
        .read_text(encoding="utf-8")
    )
    document = json.loads(content)
    return workflow_definition_from_document(document)


def workflow_definition_from_document(document: dict[str, Any]) -> WorkflowDefinition:
    """Validate JSON configuration into immutable typed domain objects."""
    try:
        transitions = tuple(
            Transition(
                name=item["name"],
                command_type=item["command_type"],
                from_state=WorkflowState(item["from_state"]),
                to_state=WorkflowState(item["to_state"]),
                guards=tuple(item.get("guards", [])),
                effects=tuple(item.get("effects", [])),
            )
            for item in document["transitions"]
        )
        return WorkflowDefinition(
            definition_id=document["definition_id"],
            version=document["version"],
            notice=document["notice"],
            transitions=transitions,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise DomainInvariantError("invalid workflow definition document") from error
