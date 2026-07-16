"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Clock3,
} from "lucide-react";
import { formatTimestamp } from "@web/shared/formatting";
import type { DecisionView } from "@web/features/clinical-reasoning/model";
import type {
  WorkflowAlertView,
  WorkflowOperationsView,
  WorkflowTaskView,
} from "./model";

interface WorkflowStage {
  id: string;
  label: string;
  status: string;
  time?: string | null;
  owner: string;
  source: string;
  quality: string;
  nextAction: string;
  href: string;
}

const stageTemplate = [
  ["patient", "Patient and Encounter"],
  ["triage", "Triage and Vitals"],
  ["ecg-acquisition", "ECG Acquisition"],
  ["ecg-ai", "ECG AI-supported Analysis"],
  ["physician-ecg", "Physician ECG Interpretation"],
  ["troponin-t0", "Troponin T0"],
  ["repeat-evidence", "Repeat Evidence"],
  ["snapshot", "Clinical Evidence Snapshot"],
  ["assessment", "Physician Assessment"],
  ["decision", "Physician Decision"],
  ["workflow", "Workflow and Tasks"],
  ["scheduling", "Follow-up Scheduling"],
  ["outcome", "Outcome and Audit"],
] as const;

export function ClinicalWorkflowBoard({
  caseId,
  value,
  decisions,
  activeTasks,
  alerts,
}: {
  caseId: string;
  value: WorkflowOperationsView;
  decisions: DecisionView[];
  activeTasks: WorkflowTaskView[];
  alerts: WorkflowAlertView[];
}) {
  const effectiveDecision = decisions.find((decision) => decision.effective);
  const stages = buildStages(
    caseId,
    value,
    activeTasks,
    alerts,
    effectiveDecision,
  );
  const selectedStage =
    stages.find((stage) => stage.status === "overdue") ??
    stages.find((stage) => stage.status === "in progress") ??
    stages.find((stage) => stage.status === "under review") ??
    stages.find((stage) => stage.status === "pending") ??
    stages[0] ??
    fallbackStage(caseId);

  return (
    <section
      className="vm-clinical-board"
      aria-labelledby="clinical-workflow-board-title"
    >
      <div className="vm-clinical-board__intro">
        <div>
          <p className="vm-eyebrow">Clinical workflow board</p>
          <h3 id="clinical-workflow-board-title">
            Evidence and physician-directed operations
          </h3>
          <p>
            Operational board only. It visualizes persisted evidence, physician
            authority and workflow tasks; it does not choose a diagnostic path.
          </p>
        </div>
        <span className="vm-status-pill vm-status-pill--technically-limited">
          Demonstration workflow
        </span>
      </div>

      <div className="vm-clinical-board__layout">
        <ol className="vm-workflow-rail" aria-label="ACS workflow stages">
          {stages.map((stage) => (
            <li key={stage.id}>
              <Link
                href={stage.href}
                className={`vm-stage-card is-${stage.status.replaceAll(" ", "-")}`}
              >
                <span className="vm-stage-card__marker" aria-hidden="true" />
                <strong>{stage.label}</strong>
                <span>{stage.status}</span>
                {stage.time ? (
                  <small>{formatTimestamp(stage.time)}</small>
                ) : null}
              </Link>
            </li>
          ))}
        </ol>

        <div className="vm-branch-board" aria-label="Current workflow branches">
          <BranchCard
            title="Active physician-directed tasks"
            icon={<Clock3 size={17} aria-hidden />}
            status={activeTasks.length ? "in progress" : "not started"}
            detail={`${activeTasks.length} active task(s).`}
            href={`/cases/${caseId}/workflow`}
          >
            {activeTasks.length ? (
              activeTasks
                .slice(0, 4)
                .map((task) => (
                  <BranchItem
                    key={task.task_id}
                    title={taskLabel(task.task_type)}
                    status={task.status}
                    detail={
                      task.due_at
                        ? `Due ${formatTimestamp(task.due_at)}`
                        : "No due time recorded"
                    }
                    source={task.source_type}
                  />
                ))
            ) : (
              <p>No active operational task has been generated.</p>
            )}
          </BranchCard>

          <BranchCard
            title="Review alerts"
            icon={<AlertTriangle size={17} aria-hidden />}
            status={alerts.length ? "under review" : "available"}
            detail={`${alerts.length} unresolved alert(s).`}
            href={`/cases/${caseId}/workflow`}
          >
            {alerts.length ? (
              alerts
                .slice(0, 3)
                .map((alert) => (
                  <BranchItem
                    key={alert.alert_id}
                    title={formatCode(alert.alert_type)}
                    status={alert.status}
                    detail={alert.message}
                    source={alert.source}
                  />
                ))
            ) : (
              <p>No unresolved workflow alert is currently recorded.</p>
            )}
          </BranchCard>

          <BranchCard
            title="Follow-up scheduling"
            icon={<CalendarClock size={17} aria-hidden />}
            status={schedulingStatus(effectiveDecision)}
            detail="Physician recommendation -> appointment request -> staff confirmation -> reminder -> completion/missed state."
            href={`/cases/${caseId}/timeline`}
          >
            <ol className="vm-schedule-flow">
              <li>Physician recommendation</li>
              <li>Administrative appointment request</li>
              <li>Specialty/service and requested window</li>
              <li>Confirmation, reminder, reschedule/cancel</li>
              <li>Missed/no-show or completed follow-up</li>
            </ol>
            <small>
              Scheduling engine and hospital calendar integration are not
              implemented in this MVP. Emergency findings remain outside normal
              scheduling.
            </small>
          </BranchCard>
        </div>

        <aside
          className="vm-board-detail"
          aria-label="Selected workflow detail"
        >
          <h3>{selectedStage.label}</h3>
          <dl>
            <dt>Status</dt>
            <dd>{selectedStage.status}</dd>
            <dt>Responsible owner</dt>
            <dd>{selectedStage.owner}</dd>
            <dt>Evidence source</dt>
            <dd>{selectedStage.source}</dd>
            <dt>Quality or limitation</dt>
            <dd>{selectedStage.quality}</dd>
            <dt>Next action</dt>
            <dd>{selectedStage.nextAction}</dd>
          </dl>
          <Link className="vm-button" href={selectedStage.href}>
            Open source workspace
          </Link>
        </aside>
      </div>
    </section>
  );
}

function buildStages(
  caseId: string,
  value: WorkflowOperationsView,
  activeTasks: WorkflowTaskView[],
  alerts: WorkflowAlertView[],
  decision?: DecisionView,
): WorkflowStage[] {
  const taskByType = new Map(activeTasks.map((task) => [task.task_type, task]));
  const hasRepeatTask =
    taskByType.has("repeat_ecg") || taskByType.has("repeat_troponin");
  const hasOverdue = activeTasks.some((task) => task.status === "overdue");
  return stageTemplate.map(([id, label]) => {
    const href = hrefForStage(caseId, id);
    const base = {
      id,
      label,
      owner: ownerForStage(id),
      source: sourceForStage(id),
      quality: "No technical limitation surfaced in this board.",
      nextAction: "Review source workspace.",
      href,
    };
    if (id === "workflow") {
      return {
        ...base,
        status: hasOverdue
          ? "overdue"
          : activeTasks.length
            ? "in progress"
            : "available",
        time: activeTasks[0]?.due_at ?? null,
        quality: alerts.length
          ? `${alerts.length} unresolved alert(s)`
          : "No unresolved workflow alert.",
        nextAction: activeTasks.length
          ? "Work through active physician-directed tasks."
          : "Await physician-directed operational task.",
      };
    }
    if (id === "decision") {
      return {
        ...base,
        status: decision ? "available" : "pending",
        time: decision?.recorded_at ?? null,
        quality: decision
          ? "Current non-revoked physician-authored decision."
          : "No effective physician decision available.",
        nextAction: decision
          ? "Generate operational work only when appropriate."
          : "Record physician decision in Clinical Reasoning.",
      };
    }
    if (id === "repeat-evidence") {
      return {
        ...base,
        status: hasRepeatTask ? "in progress" : "not started",
        time:
          taskByType.get("repeat_ecg")?.due_at ??
          taskByType.get("repeat_troponin")?.due_at ??
          null,
        quality: hasRepeatTask
          ? "Repeat evidence requested by persisted workflow task."
          : "No repeat evidence task currently active.",
        nextAction: hasRepeatTask
          ? "Complete repeat evidence through the owning ECG or Troponin workspace."
          : "No action unless physician requests repeat evidence.",
      };
    }
    if (id === "scheduling") {
      return {
        ...base,
        status: schedulingStatus(decision),
        quality:
          "Scheduling is represented, not automated, in the current MVP.",
        nextAction:
          "Use outcome/timeline documentation until a scheduling module exists.",
      };
    }
    return {
      ...base,
      status: inferredStageStatus(id, value, decision),
      nextAction: nextActionForStage(id),
    };
  });
}

function fallbackStage(caseId: string): WorkflowStage {
  return {
    id: "workflow",
    label: "Workflow and Tasks",
    status: "pending",
    owner: "Clinical team",
    source: "Workflow operations",
    quality: "Workflow projection unavailable.",
    nextAction: "Refresh the workflow workspace.",
    href: `/cases/${caseId}/workflow`,
  };
}

function inferredStageStatus(
  id: string,
  value: WorkflowOperationsView,
  decision?: DecisionView,
) {
  if (id === "assessment") return decision ? "available" : "pending";
  if (id === "snapshot") return decision ? "available" : "pending";
  if (id === "outcome")
    return value.workflow.state === "closed" ? "completed" : "pending";
  if (
    [
      "patient",
      "triage",
      "ecg-acquisition",
      "ecg-ai",
      "physician-ecg",
      "troponin-t0",
    ].includes(id)
  ) {
    return "available";
  }
  return "pending";
}

function schedulingStatus(decision?: DecisionView) {
  return decision?.decision_type === "other_documented_plan"
    ? "pending"
    : "not started";
}

function hrefForStage(caseId: string, id: string) {
  if (id === "triage") return `/cases/${caseId}/documentation`;
  if (id.startsWith("ecg") || id === "physician-ecg")
    return `/cases/${caseId}/ecg`;
  if (id === "troponin-t0" || id === "repeat-evidence")
    return `/cases/${caseId}/troponin`;
  if (["snapshot", "assessment", "decision"].includes(id))
    return `/cases/${caseId}/clinical-reasoning`;
  if (id === "workflow") return `/cases/${caseId}/workflow`;
  if (id === "outcome" || id === "scheduling")
    return `/cases/${caseId}/timeline`;
  return `/cases/${caseId}`;
}

function ownerForStage(id: string) {
  if (id.includes("physician") || ["assessment", "decision"].includes(id)) {
    return "Physician";
  }
  if (id === "scheduling")
    return "Administrative staff after physician recommendation";
  if (id === "workflow") return "Assigned operational owner or team";
  return "Clinical team";
}

function sourceForStage(id: string) {
  if (id.includes("ecg")) return "ECG workspace";
  if (id.includes("troponin")) return "Troponin workspace";
  if (id === "scheduling") return "Outcome/Timeline representation";
  if (id === "workflow") return "Workflow operations";
  return "Case workspace";
}

function nextActionForStage(id: string) {
  if (id === "triage") return "Review or correct documentation.";
  if (id === "ecg-ai") return "Run or review model inference with provenance.";
  if (id === "physician-ecg") return "Record physician ECG interpretation.";
  if (id === "troponin-t0")
    return "Review serial result and delta owner output.";
  if (id === "assessment") return "Record physician assessment.";
  return "Review source workspace.";
}

function BranchCard({
  title,
  status,
  detail,
  icon,
  href,
  children,
}: {
  title: string;
  status: string;
  detail: string;
  icon: ReactNode;
  href: string;
  children: ReactNode;
}) {
  return (
    <article className="vm-branch-card">
      <header>
        <span aria-hidden="true">{icon}</span>
        <div>
          <h4>{title}</h4>
          <p>{detail}</p>
        </div>
        <span
          className={`vm-status-pill vm-status-pill--${status.replaceAll(" ", "-")}`}
        >
          {status}
        </span>
      </header>
      <div>{children}</div>
      <Link href={href}>Open source workspace</Link>
    </article>
  );
}

function BranchItem({
  title,
  status,
  detail,
  source,
}: {
  title: string;
  status: string;
  detail: string;
  source: string;
}) {
  return (
    <div className="vm-branch-item">
      <CheckCircle2 size={15} aria-hidden />
      <div>
        <strong>{title}</strong>
        <p>{detail}</p>
        <small>
          {formatCode(status)} - {formatCode(source)}
        </small>
      </div>
    </div>
  );
}

function taskLabel(code: string) {
  const labels: Record<string, string> = {
    repeat_ecg: "Repeat ECG",
    repeat_troponin: "Repeat troponin",
    obtain_additional_information: "Obtain additional information",
    cardiology_review: "Cardiology review",
    cath_lab_review: "Physician request for cath-lab review",
    physician_reassessment: "Physician reassessment",
  };
  return labels[code] ?? formatCode(code);
}

function formatCode(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
