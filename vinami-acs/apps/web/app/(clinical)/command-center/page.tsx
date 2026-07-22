import type { Metadata } from "next";
import { PageHeader } from "@vinami/ui";
import {
  CommandCenter,
  type CommandCenterState,
} from "@web/features/command-center/command-center";
import { loadCommandCenter } from "@web/features/command-center/server-data";
import { ErrorPanel } from "@web/shared/ui/error-panel";
import { presentError } from "@web/shared/errors/presentation";

export const metadata: Metadata = { title: "Trung tâm điều phối" };

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
    owner: owner(single(params.owner)),
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
          eyebrow="Điều phối lâm sàng"
          title="Trung tâm điều phối"
          description="Danh sách ca nghi hội chứng mạch vành cấp đang hoạt động, được ưu tiên từ trạng thái quy trình, công việc, cảnh báo và bằng chứng đã lưu. Bác sĩ vẫn là người xác nhận mọi quyết định hệ quả."
        />
        <CommandCenter initialData={initialData} initialState={state} />
      </>
    );
  } catch (error) {
    return (
      <>
        <PageHeader eyebrow="Điều phối lâm sàng" title="Trung tâm điều phối" />
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
function owner(value: string): string {
  const trimmed = value.trim();
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    trimmed,
  )
    ? trimmed
    : "";
}
function sort(value: string): CommandCenterState["sort"] {
  return ["priority", "opened_at", "next_due_at", "latest_activity"].includes(
    value,
  )
    ? (value as CommandCenterState["sort"])
    : "priority";
}
