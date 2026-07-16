"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import {
  AlertTriangle,
  BellRing,
  Clock3,
  History,
  ListChecks,
  UserRoundCheck,
} from "lucide-react";
import { createBrowserApiClient } from "@web/shared/api/browser";
import { formatTimestamp } from "@web/shared/formatting";
import type { DecisionView } from "@web/features/clinical-reasoning/model";
import {
  workflowOperationsSchema,
  type WorkflowAlertView,
  type WorkflowOperationsView,
  type WorkflowTaskView,
} from "./model";

const taskLabels: Record<string, string> = {
  repeat_ecg: "Repeat ECG",
  repeat_troponin: "Repeat troponin",
  obtain_additional_information: "Obtain additional information",
  cardiology_review: "Cardiology review",
  cath_lab_review: "Physician request for cath-lab review",
  physician_reassessment: "Physician reassessment",
  other_documented_task: "Other documented task",
};

const actionableDecisions = new Set([
  "request_repeat_ecg",
  "request_repeat_troponin",
  "request_additional_information",
  "request_cardiology_review",
  "request_cath_lab_review",
  "other_documented_plan",
]);

type TaskAction = "assign" | "acknowledge" | "start" | "complete" | "cancel";
type AlertAction = "acknowledge" | "resolve";
type GenerateForm = {
  priority: "routine" | "priority" | "urgent";
  dueAt: string;
};
type ReasonForm = { reason: string };

export function WorkflowOperationsWorkspace({
  caseId,
  actorId,
  initialValue,
  decisions,
}: {
  caseId: string;
  actorId: string;
  initialValue: WorkflowOperationsView;
  decisions: DecisionView[];
}) {
  const api = useMemo(() => createBrowserApiClient(), []);
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["workflow-operations", caseId],
    initialData: initialValue,
    queryFn: async () =>
      workflowOperationsSchema.parse(
        await api.getWorkflowOperationsWorkspace(caseId),
      ),
  });
  const value = query.data;
  const [selectedDecision, setSelectedDecision] = useState<DecisionView | null>(
    null,
  );
  const [taskAction, setTaskAction] = useState<{
    task: WorkflowTaskView;
    action: TaskAction;
  } | null>(null);
  const [alertAction, setAlertAction] = useState<{
    alert: WorkflowAlertView;
    action: AlertAction;
  } | null>(null);
  const generateForm = useForm<GenerateForm>({
    defaultValues: { priority: "routine", dueAt: "" },
  });
  const reasonForm = useForm<ReasonForm>({ defaultValues: { reason: "" } });
  const refresh = () =>
    queryClient.invalidateQueries({
      queryKey: ["workflow-operations", caseId],
    });

  const generateMutation = useMutation({
    mutationFn: async (form: GenerateForm) => {
      if (!selectedDecision) throw new Error("Select a physician decision.");
      return api.generateWorkflowTask(
        caseId,
        {
          decision_id: selectedDecision.decision_id,
          expected_decision_version: selectedDecision.record_version,
          expected_workflow_version: value.workflow.version,
          priority: form.priority,
          due_at: form.dueAt ? new Date(form.dueAt).toISOString() : null,
        },
        crypto.randomUUID(),
      );
    },
    onSuccess: async () => {
      setSelectedDecision(null);
      generateForm.reset();
      await refresh();
    },
  });
  const taskMutation = useMutation({
    mutationFn: async (form: ReasonForm) => {
      if (!taskAction) throw new Error("Select a task action.");
      return api.changeWorkflowTask(
        caseId,
        taskAction.task.task_id,
        taskAction.action,
        {
          expected_version: taskAction.task.version,
          owner_user_id: taskAction.action === "assign" ? actorId : null,
          owner_team_id: null,
          reason:
            taskAction.action === "complete" || taskAction.action === "cancel"
              ? form.reason
              : null,
        },
        crypto.randomUUID(),
      );
    },
    onSuccess: async () => {
      setTaskAction(null);
      reasonForm.reset();
      await refresh();
    },
  });
  const alertMutation = useMutation({
    mutationFn: async (form: ReasonForm) => {
      if (!alertAction) throw new Error("Select an alert action.");
      return api.changeWorkflowAlert(
        caseId,
        alertAction.alert.alert_id,
        alertAction.action,
        {
          expected_version: alertAction.alert.version,
          reason: alertAction.action === "resolve" ? form.reason : null,
        },
        crypto.randomUUID(),
      );
    },
    onSuccess: async () => {
      setAlertAction(null);
      reasonForm.reset();
      await refresh();
    },
  });
  const overdueMutation = useMutation({
    mutationFn: () => api.evaluateWorkflowOverdue(caseId, crypto.randomUUID()),
    onSuccess: refresh,
  });

  const activeTasks = value.tasks.filter(
    (task) => !["completed", "cancelled"].includes(task.status),
  );
  const historicalTasks = value.tasks.filter((task) =>
    ["completed", "cancelled"].includes(task.status),
  );
  const availableDecisions = decisions.filter(
    (decision) =>
      decision.effective &&
      actionableDecisions.has(decision.decision_type) &&
      !value.tasks.some(
        (task) => task.originating_decision_id === decision.decision_id,
      ),
  );

  return (
    <main className="vm-workflow-workspace">
      <section className="vm-card vm-workflow-hero">
        <div className="vm-card__body">
          <div>
            <p className="vm-eyebrow">Operational workflow</p>
            <h2>{formatCode(value.workflow.state)}</h2>
            <p>
              Workflow v{value.workflow.version} · Definition{" "}
              {value.workflow.definition_version}
            </p>
          </div>
          <button
            className="vm-button"
            disabled={overdueMutation.isPending}
            onClick={() => overdueMutation.mutate()}
          >
            <Clock3 size={16} /> Evaluate due times
          </button>
        </div>
        <p className="vm-safety-note">{value.safety_notice}</p>
        <p className="vm-demo-notice">{value.workflow.demonstration_notice}</p>
      </section>

      <div className="vm-workflow-summary" aria-label="Workflow summary">
        <Metric label="Active tasks" value={activeTasks.length} />
        <Metric
          label="Overdue / escalated"
          value={activeTasks.filter((task) => task.status === "overdue").length}
        />
        <Metric
          label="Unresolved alerts"
          value={
            value.alerts.filter((alert) => alert.status !== "resolved").length
          }
        />
        <Metric label="Completed / cancelled" value={historicalTasks.length} />
      </div>

      <section className="vm-card">
        <div className="vm-card__body">
          <div className="vm-section-heading">
            <div>
              <h3>Physician-authored requests awaiting operationalization</h3>
              <p>
                Tasks can only be generated from effective persisted decisions.
              </p>
            </div>
          </div>
          {!availableDecisions.length && (
            <p>No unprocessed physician request is currently available.</p>
          )}
          {availableDecisions.map((decision) => (
            <article className="vm-workflow-row" key={decision.decision_id}>
              <div>
                <strong>{decisionLabel(decision.decision_type)}</strong>
                <p>{decision.rationale}</p>
                <small>Recorded {formatTimestamp(decision.recorded_at)}</small>
              </div>
              <button
                className="vm-button vm-button--primary"
                onClick={() => setSelectedDecision(decision)}
              >
                Create operational task
              </button>
            </article>
          ))}
        </div>
      </section>

      <section className="vm-card" aria-labelledby="active-task-heading">
        <div className="vm-card__body">
          <h3 id="active-task-heading">
            <ListChecks size={18} /> Active tasks
          </h3>
          {!activeTasks.length && <p>No active operational task.</p>}
          <div className="vm-workflow-list">
            {activeTasks.map((task) => (
              <TaskCard
                key={task.task_id}
                task={task}
                onAction={(action) => {
                  reasonForm.reset();
                  setTaskAction({ task, action });
                }}
              />
            ))}
          </div>
        </div>
      </section>

      <section className="vm-card" aria-labelledby="alert-heading">
        <div className="vm-card__body">
          <h3 id="alert-heading">
            <BellRing size={18} /> Alerts requiring human review
          </h3>
          {!value.alerts.length && <p>No operational alert recorded.</p>}
          {value.alerts.map((alert) => (
            <article
              className={`vm-alert-row vm-alert-row--${alert.severity}`}
              key={alert.alert_id}
            >
              <div>
                <strong>{formatCode(alert.alert_type)}</strong>
                <p>{alert.message}</p>
                <small>
                  {alert.status} · v{alert.version} ·{" "}
                  {formatTimestamp(alert.raised_at)}
                </small>
              </div>
              <div className="vm-inline-actions">
                {alert.status === "active" && (
                  <button
                    className="vm-button"
                    onClick={() =>
                      setAlertAction({ alert, action: "acknowledge" })
                    }
                  >
                    Acknowledge
                  </button>
                )}
                {alert.status === "acknowledged" && (
                  <button
                    className="vm-button"
                    onClick={() => setAlertAction({ alert, action: "resolve" })}
                  >
                    Resolve
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="vm-card">
        <div className="vm-card__body">
          <h3>
            <History size={18} /> Completed and cancelled history
          </h3>
          {!historicalTasks.length && <p>No completed or cancelled task.</p>}
          {historicalTasks.map((task) => (
            <article className="vm-workflow-row" key={task.task_id}>
              <div>
                <strong>{taskLabel(task.task_type)}</strong>
                <p>{task.outcome ?? task.cancellation_reason}</p>
              </div>
              <span className={`vm-status-pill vm-status-pill--${task.status}`}>
                {task.status}
              </span>
            </article>
          ))}
        </div>
      </section>

      <nav
        className="vm-card vm-reasoning-links"
        aria-label="Related workflow records"
      >
        <Link href={`/cases/${caseId}/clinical-reasoning`}>
          Clinical Reasoning
        </Link>
        <Link href={`/cases/${caseId}/timeline`}>Timeline</Link>
        <Link href={`/cases/${caseId}/audit`}>Audit</Link>
      </nav>

      {selectedDecision && (
        <Dialog
          title="Create operational task"
          onCancel={() => setSelectedDecision(null)}
        >
          <form
            className="vm-form-stack"
            onSubmit={generateForm.handleSubmit((form) =>
              generateMutation.mutate(form),
            )}
          >
            <p>
              <strong>{decisionLabel(selectedDecision.decision_type)}</strong>
            </p>
            <label>
              Priority
              <select {...generateForm.register("priority")}>
                <option value="routine">Routine</option>
                <option value="priority">Priority</option>
                <option value="urgent">Urgent</option>
              </select>
            </label>
            <label>
              Due time (optional)
              <input
                type="datetime-local"
                {...generateForm.register("dueAt")}
              />
            </label>
            <p>
              This task records operational work only. It does not create a
              diagnosis, treatment instruction, or case closure.
            </p>
            <button
              className="vm-button vm-button--primary"
              disabled={generateMutation.isPending}
            >
              Confirm task creation
            </button>
            <MutationError error={generateMutation.error} />
          </form>
        </Dialog>
      )}

      {taskAction && (
        <Dialog
          title={`${formatCode(taskAction.action)} task`}
          onCancel={() => setTaskAction(null)}
        >
          <form
            className="vm-form-stack"
            onSubmit={reasonForm.handleSubmit((form) =>
              taskMutation.mutate(form),
            )}
          >
            <p>
              <strong>{taskLabel(taskAction.task.task_type)}</strong>
            </p>
            {taskAction.action === "assign" && (
              <p>
                <UserRoundCheck size={16} /> Assign this task to your verified
                identity.
              </p>
            )}
            {["complete", "cancel"].includes(taskAction.action) && (
              <label>
                Required reason
                <textarea
                  {...reasonForm.register("reason", { required: true })}
                />
              </label>
            )}
            <button
              className="vm-button vm-button--primary"
              disabled={taskMutation.isPending}
            >
              Confirm {taskAction.action}
            </button>
            <MutationError error={taskMutation.error} />
          </form>
        </Dialog>
      )}

      {alertAction && (
        <Dialog
          title={`${formatCode(alertAction.action)} alert`}
          onCancel={() => setAlertAction(null)}
        >
          <form
            className="vm-form-stack"
            onSubmit={reasonForm.handleSubmit((form) =>
              alertMutation.mutate(form),
            )}
          >
            <p>{alertAction.alert.message}</p>
            {alertAction.action === "resolve" && (
              <label>
                Resolution reason
                <textarea
                  {...reasonForm.register("reason", { required: true })}
                />
              </label>
            )}
            <p>
              Acknowledgement and resolution do not replace clinical authority.
            </p>
            <button
              className="vm-button vm-button--primary"
              disabled={alertMutation.isPending}
            >
              Confirm {alertAction.action}
            </button>
            <MutationError error={alertMutation.error} />
          </form>
        </Dialog>
      )}
    </main>
  );
}

function TaskCard({
  task,
  onAction,
}: {
  task: WorkflowTaskView;
  onAction: (action: TaskAction) => void;
}) {
  const actions: Record<string, TaskAction[]> = {
    pending: ["assign", "cancel"],
    assigned: ["acknowledge", "cancel"],
    acknowledged: ["start", "cancel"],
    overdue: ["start", "cancel"],
    in_progress: ["complete", "cancel"],
  };
  return (
    <article className={`vm-task-card vm-task-card--${task.status}`}>
      <div className="vm-task-card__header">
        <div>
          <span
            className={`vm-priority-pill vm-priority-pill--${task.priority}`}
          >
            {task.priority}
          </span>
          <h4>{taskLabel(task.task_type)}</h4>
        </div>
        <span className={`vm-status-pill vm-status-pill--${task.status}`}>
          {formatCode(task.status)}
        </span>
      </div>
      <dl>
        <dt>Due</dt>
        <dd>{task.due_at ? formatTimestamp(task.due_at) : "Not specified"}</dd>
        <dt>Owner</dt>
        <dd>
          {task.owner_user_id
            ? "Assigned user"
            : task.owner_team_id
              ? "Assigned team"
              : "Unassigned"}
        </dd>
        <dt>Escalation</dt>
        <dd>{task.escalation_level}</dd>
        <dt>Origin</dt>
        <dd>
          {task.originating_decision?.rationale ?? "Persisted workflow effect"}
        </dd>
      </dl>
      <div className="vm-inline-actions">
        {(actions[task.status] ?? []).map((action) => (
          <button
            className={
              action === "cancel" ? "vm-button vm-button--danger" : "vm-button"
            }
            key={action}
            onClick={() => onAction(action)}
          >
            {formatCode(action)}
          </button>
        ))}
      </div>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
function Dialog({
  title,
  onCancel,
  children,
}: {
  title: string;
  onCancel: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="vm-dialog-backdrop" role="presentation">
      <div
        className="vm-confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="workflow-dialog-title"
      >
        <div className="vm-section-heading">
          <h3 id="workflow-dialog-title">{title}</h3>
          <button className="vm-button" onClick={onCancel}>
            Close
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
function MutationError({ error }: { error: Error | null }) {
  return error ? (
    <p className="vm-warning" role="alert">
      <AlertTriangle size={16} /> {error.message}
    </p>
  ) : null;
}
function taskLabel(code: string) {
  return taskLabels[code] ?? formatCode(code);
}
function decisionLabel(code: string) {
  return code === "request_cath_lab_review"
    ? "Physician request for cath-lab review"
    : formatCode(code);
}
function formatCode(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
