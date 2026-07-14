import type { Metadata } from "next";
import { PageHeader } from "@vinami/ui";
import {
  CommandCenter,
  type CommandCenterState,
} from "@web/features/command-center/command-center";
import { loadCaseQueue } from "@web/features/command-center/server-data";
import { ErrorPanel } from "@web/shared/ui/error-panel";
import { presentError } from "@web/shared/errors/presentation";

export const metadata: Metadata = { title: "Command Center" };

export default async function CommandCenterPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const state: CommandCenterState = {
    status: statusFilter(single(params.status)),
    priority: priorityFilter(single(params.priority)),
    location: single(params.location),
    search: single(params.q),
    page: positiveInteger(single(params.page), 1),
    pageSize: 25,
    selected: single(params.selected) || undefined,
  };
  try {
    const initialData = await loadCaseQueue({
      page: state.page,
      page_size: state.pageSize,
      status: state.status || undefined,
      priority: state.priority || undefined,
      location: state.location || undefined,
    });
    return (
      <>
        <PageHeader
          eyebrow="Clinical operations"
          title="Active Clinical Case Queue"
          description="Suspected ACS lifecycle cases persisted by the R1 system of record. Select a case to review its verified context."
        />
        <CommandCenter initialData={initialData} initialState={state} />
      </>
    );
  } catch (error) {
    return (
      <>
        <PageHeader
          eyebrow="Clinical operations"
          title="Active Clinical Case Queue"
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
function statusFilter(value: string): CommandCenterState["status"] {
  return ["open", "under_review", "closed"].includes(value)
    ? (value as CommandCenterState["status"])
    : "";
}
function priorityFilter(value: string): CommandCenterState["priority"] {
  return ["routine", "urgent", "critical"].includes(value)
    ? (value as CommandCenterState["priority"])
    : "";
}
