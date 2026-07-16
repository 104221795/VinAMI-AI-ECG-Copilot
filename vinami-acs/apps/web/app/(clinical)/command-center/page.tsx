import type { Metadata } from "next";
import { PageHeader } from "@vinami/ui";
import {
  CommandCenter,
  type CommandCenterState,
} from "@web/features/command-center/command-center";
import { loadCommandCenter } from "@web/features/command-center/server-data";
import { ErrorPanel } from "@web/shared/ui/error-panel";
import { presentError } from "@web/shared/errors/presentation";

export const metadata: Metadata = { title: "Advanced Command Center" };

export default async function CommandCenterPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const state: CommandCenterState = {
    priority: priority(single(params.priority)),
    workflowState: workflowState(single(params.workflow_state)),
    overdue: overdue(single(params.overdue)),
    alertStatus: alertStatus(single(params.alert_status)),
    evidenceStatus: evidenceStatus(single(params.evidence_status)),
    owner: single(params.owner),
    sort: sort(single(params.sort)),
    direction: single(params.direction) === "asc" ? "asc" : "desc",
    page: positiveInteger(single(params.page), 1),
    pageSize: 25,
    selected: single(params.selected) || undefined,
  };
  try {
    const initialData = await loadCommandCenter({
      page: state.page,
      page_size: state.pageSize,
      priority: state.priority || undefined,
      workflow_state: state.workflowState || undefined,
      overdue: state.overdue ? state.overdue === "true" : undefined,
      alert_status: state.alertStatus || undefined,
      evidence_status: state.evidenceStatus || undefined,
      owner_id: state.owner || undefined,
      sort: state.sort,
      direction: state.direction,
    });
    return (
      <>
        <PageHeader
          eyebrow="Clinical operations"
          title="Advanced Command Center"
          description="Active suspected ACS cases prioritized from persisted workflow, task, alert and evidence state. Physician review remains the authority for consequential decisions."
        />
        <CommandCenter initialData={initialData} initialState={state} />
      </>
    );
  } catch (error) {
    return (
      <>
        <PageHeader
          eyebrow="Clinical operations"
          title="Advanced Command Center"
        />
        <ErrorPanel presentation={presentError(error)} />
      </>
    );
  }
}

function single(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}
function positiveInteger(value: string, fallback: number): number {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}
function priority(value: string): CommandCenterState["priority"] {
  return ["routine", "urgent", "critical"].includes(value)
    ? (value as CommandCenterState["priority"])
    : "";
}
function workflowState(value: string): CommandCenterState["workflowState"] {
  const states: CommandCenterState["workflowState"][] = [
    "NEW",
    "TRIAGE_IN_PROGRESS",
    "AWAITING_ECG",
    "ECG_UNDER_REVIEW",
    "AWAITING_TROPONIN",
    "OBSERVATION",
    "PHYSICIAN_REVIEW_REQUIRED",
    "PATHWAY_SELECTED",
    "TRANSFER_IN_PROGRESS",
    "CATH_LAB_REVIEW",
    "DISCHARGE_REVIEW",
    "CLOSED",
    "CANCELLED",
  ];
  return states.includes(value as CommandCenterState["workflowState"])
    ? (value as CommandCenterState["workflowState"])
    : "";
}
function overdue(value: string): CommandCenterState["overdue"] {
  return value === "true" || value === "false" ? value : "";
}
function alertStatus(value: string): CommandCenterState["alertStatus"] {
  return ["active", "acknowledged", "unresolved", "none"].includes(value)
    ? (value as CommandCenterState["alertStatus"])
    : "";
}
function evidenceStatus(value: string): CommandCenterState["evidenceStatus"] {
  return ["current", "missing", "stale", "technical_limit"].includes(value)
    ? (value as CommandCenterState["evidenceStatus"])
    : "";
}
function sort(value: string): CommandCenterState["sort"] {
  return ["priority", "opened_at", "next_due_at", "latest_activity"].includes(
    value,
  )
    ? (value as CommandCenterState["sort"])
    : "priority";
}
