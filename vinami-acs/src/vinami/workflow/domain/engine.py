"""Guard and effect registry for declarative workflow execution."""

from __future__ import annotations

from collections.abc import Callable
from uuid import NAMESPACE_URL, UUID, uuid5

from vinami.shared.domain import DomainInvariantError
from vinami.workflow.domain.definition import (
    DueTimer,
    GeneratedAlert,
    GeneratedTask,
    Transition,
    TransitionExecution,
    WorkflowCommand,
    WorkflowDefinition,
    WorkflowFacts,
    WorkflowState,
)

Guard = Callable[[WorkflowFacts], bool]
Effect = Callable[[UUID, WorkflowCommand], tuple[GeneratedTask | GeneratedAlert | DueTimer, ...]]


class WorkflowEngine:
    """Execute configured transitions without embedding clinical policy in control flow."""

    def __init__(
        self, guards: dict[str, Guard] | None = None, effects: dict[str, Effect] | None = None
    ) -> None:
        """Compose named guard and effect registries at the domain boundary."""
        self._guards = guards or _default_guards()
        self._effects = effects or _default_effects()

    def apply(
        self,
        definition: WorkflowDefinition,
        state: WorkflowState,
        facts: WorkflowFacts,
        command: WorkflowCommand,
        workflow_id: UUID,
    ) -> TransitionExecution:
        """Select the first configured transition whose named guards all succeed."""
        updated_facts = facts.apply_patch(command.facts_patch)
        candidates = tuple(
            transition
            for transition in definition.transitions
            if transition.from_state is state and transition.command_type == command.command_type
        )
        if not candidates:
            raise DomainInvariantError(
                f"command {command.command_type} is not allowed from workflow state {state.value}"
            )
        for transition in candidates:
            if self._guards_satisfied(transition, updated_facts):
                return self._execute_effects(transition, updated_facts, command, workflow_id)
        raise DomainInvariantError(
            f"workflow guards rejected {command.command_type} from {state.value}"
        )

    def _guards_satisfied(self, transition: Transition, facts: WorkflowFacts) -> bool:
        return all(self._guard(name)(facts) for name in transition.guards)

    def _guard(self, name: str) -> Guard:
        try:
            return self._guards[name]
        except KeyError as error:
            raise DomainInvariantError(f"unknown workflow guard: {name}") from error

    def _execute_effects(
        self,
        transition: Transition,
        facts: WorkflowFacts,
        command: WorkflowCommand,
        workflow_id: UUID,
    ) -> TransitionExecution:
        tasks: list[GeneratedTask] = []
        alerts: list[GeneratedAlert] = []
        timers: list[DueTimer] = []
        for name in transition.effects:
            try:
                generated = self._effects[name](workflow_id, command)
            except KeyError as error:
                raise DomainInvariantError(f"unknown workflow effect: {name}") from error
            tasks.extend(item for item in generated if isinstance(item, GeneratedTask))
            alerts.extend(item for item in generated if isinstance(item, GeneratedAlert))
            timers.extend(item for item in generated if isinstance(item, DueTimer))
        return TransitionExecution(transition, facts, tuple(tasks), tuple(alerts), tuple(timers))


def _default_guards() -> dict[str, Guard]:
    return {
        "ecg_quality_acceptable": lambda facts: (
            facts.ecg_available and facts.ecg_quality_acceptable
        ),
        "ecg_quality_not_acceptable": lambda facts: (
            facts.ecg_available and not facts.ecg_quality_acceptable
        ),
        "troponin_available": lambda facts: facts.troponin_available,
        "troponin_rising": lambda facts: facts.troponin_available and facts.troponin_rising,
        "not_troponin_rising": lambda facts: not facts.troponin_rising,
        "no_conflicting_signals": lambda facts: not facts.conflicting_signals,
        "conflicting_signals": lambda facts: facts.conflicting_signals,
        "no_unresolved_critical_alerts": lambda facts: facts.unresolved_critical_alerts == 0,
        "missing_troponin_after_due": lambda facts: facts.missing_troponin_after_due,
        "repeat_ecg_overdue": lambda facts: facts.repeat_ecg_overdue,
    }


def _default_effects() -> dict[str, Effect]:
    def task(effect_name: str, task_type: str) -> Effect:
        return lambda workflow_id, command: (
            GeneratedTask(
                _effect_id(workflow_id, command.command_id, effect_name),
                command.command_id,
                effect_name,
                task_type,
                command.due_at,
            ),
        )

    def alert(effect_name: str, alert_type: str, message: str) -> Effect:
        return lambda workflow_id, command: (
            GeneratedAlert(
                _effect_id(workflow_id, command.command_id, effect_name),
                command.command_id,
                effect_name,
                alert_type,
                "urgent",
                message,
            ),
        )

    def troponin_due(
        workflow_id: UUID, command: WorkflowCommand
    ) -> tuple[GeneratedTask | GeneratedAlert | DueTimer, ...]:
        if command.due_at is None:
            raise DomainInvariantError("schedule_troponin_due requires an explicit due_at")
        return (
            DueTimer(
                _effect_id(workflow_id, command.command_id, "schedule_troponin_due"),
                "troponin-result-due",
                command.due_at,
                "timer_due",
                {"missing_troponin_after_due": True},
            ),
        )

    def repeat_ecg_due(
        workflow_id: UUID, command: WorkflowCommand
    ) -> tuple[GeneratedTask | GeneratedAlert | DueTimer, ...]:
        if command.due_at is None:
            return ()
        return (
            DueTimer(
                _effect_id(workflow_id, command.command_id, "schedule_repeat_ecg_due"),
                "repeat-ecg-due",
                command.due_at,
                "repeat_ecg_due",
                {"repeat_ecg_overdue": True},
            ),
        )

    return {
        "create_ecg_review_task": task("create_ecg_review_task", "ecg_review"),
        "create_troponin_task": task("create_troponin_task", "troponin_follow_up"),
        "create_physician_review_task": task("create_physician_review_task", "physician_review"),
        "create_repeat_ecg_task": task("create_repeat_ecg_task", "repeat_ecg"),
        "create_cath_lab_review_task": task("create_cath_lab_review_task", "cath_lab_review"),
        "create_transfer_task": task("create_transfer_task", "transfer_coordination"),
        "raise_poor_ecg_quality_alert": alert(
            "raise_poor_ecg_quality_alert",
            "poor_ecg_quality_requires_review",
            "ECG quality prevents normal AI interpretation; physician review is required.",
        ),
        "raise_conflicting_signals_alert": alert(
            "raise_conflicting_signals_alert",
            "conflicting_signals_require_review",
            "Conflicting ECG, troponin, or clinical signals require physician review.",
        ),
        "raise_rising_troponin_alert": alert(
            "raise_rising_troponin_alert",
            "rising_troponin_requires_review",
            "A rising troponin trend requires physician review in this demonstration workflow.",
        ),
        "raise_missing_troponin_alert": alert(
            "raise_missing_troponin_alert",
            "troponin_overdue_requires_review",
            "A scheduled troponin result is overdue; physician review is required.",
        ),
        "raise_repeat_ecg_overdue_alert": alert(
            "raise_repeat_ecg_overdue_alert",
            "repeat_ecg_overdue_requires_review",
            "A requested repeat ECG is overdue; physician review is required.",
        ),
        "raise_compensation_review_alert": alert(
            "raise_compensation_review_alert",
            "workflow_compensation_requires_review",
            "A workflow compensation operation requires physician review.",
        ),
        "schedule_troponin_due": troponin_due,
        "schedule_repeat_ecg_due": repeat_ecg_due,
    }


def _effect_id(workflow_id: UUID, command_id: UUID, effect_name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"vinami-workflow:{workflow_id}:{command_id}:{effect_name}")
