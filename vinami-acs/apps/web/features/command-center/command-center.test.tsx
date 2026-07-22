import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { CommandCenter } from "./command-center";
import { loadCommandCenterWith } from "./data";
import type { CommandCenterCaseView, CommandCenterPageView } from "./model";

vi.mock("./data", () => ({ loadCommandCenterWith: vi.fn() }));
vi.mock("@web/shared/api/browser", () => ({
  createBrowserApiClient: () => ({}),
}));
vi.mock("@web/shared/hooks/use-connectivity", () => ({
  useConnectivity: () => true,
}));
vi.mock("@web/features/realtime/use-realtime-updates", () => ({
  useRealtimeUpdates: () => ({
    state: "connected",
    lastUpdateAt: null,
    notification: null,
  }),
}));
vi.mock("@web/features/realtime/connection-status", () => ({
  RealtimeStatus: () => null,
}));
vi.mock("@web/features/realtime/integration-status-panel", () => ({
  IntegrationStatusPanel: () => null,
}));

const baseRow: CommandCenterCaseView = {
  case_id: "cbbc0872-798f-40c5-83e3-64d66176e73b",
  encounter_id: "2a46ec31-5371-4424-99f0-c3aee1399e69",
  patient_id: "8b78f75f-dfce-4ed4-948a-b25e186b645a",
  patient_reference: "SYN-R7-001",
  age_band: "45-64",
  sex_at_birth: "female",
  location: "Emergency Department",
  case_status: "open",
  case_priority: "urgent",
  case_version: 2,
  opened_at: "2026-07-15T14:00:00Z",
  workflow_id: "ac2d5e2c-2ea2-4b60-8070-a33c91fbc359",
  workflow_state: "NEW",
  workflow_version: 1,
  operational_priority: "urgent",
  priority_reason: "Human-recorded urgent case priority",
  active_task_count: 0,
  overdue_task_count: 0,
  unresolved_alert_count: 0,
  next_due_at: null,
  oldest_overdue_at: null,
  owner_user_id: null,
  owner_team_id: null,
  snapshot_id: null,
  snapshot_created_at: null,
  evidence_status: "missing",
  evidence_freshness: { triage: "missing" },
  missing_evidence: ["triage"],
  technical_limits: [],
  decision_id: null,
  decision_type: null,
  decision_rationale: null,
  decision_recorded_at: null,
  latest_activity_at: "2026-07-15T14:00:00Z",
  update_token: "page-1",
  tasks: [],
  alerts: [],
  automation: {
    policy_version: "vinami-r13-r14-r21-demo-v1",
    safety_notice: "Demonstration automation - not for clinical use.",
    completeness: {
      score: 50,
      status: "incomplete",
      required_count: 6,
      current_count: 3,
      items: [],
      missing_evidence: ["triage"],
      stale_evidence: [],
      technical_limits: [],
      not_negative_evidence_notice:
        "Missing, unknown, stale, or technically limited evidence is not negative evidence.",
    },
    suggested_tasks: [],
    alert_digest: [],
  },
};

function page(
  row: CommandCenterCaseView,
  pageNumber: number,
): CommandCenterPageView {
  return {
    items: [row],
    page: pageNumber,
    page_size: 1,
    total: 2,
    evaluated_at: "2026-07-15T15:00:00Z",
  };
}

function Wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      {children}
    </QueryClientProvider>
  );
}

describe("CommandCenter query state", () => {
  it("fetches a new authoritative page instead of reusing the first initialData page", async () => {
    const secondRow: CommandCenterCaseView = {
      ...baseRow,
      case_id: "ab220872-798f-40c5-83e3-64d66176e73b",
      patient_reference: "SYN-R7-002",
      update_token: "page-2",
    };
    vi.mocked(loadCommandCenterWith).mockImplementation(async (_api, query) =>
      page(query.page === 2 ? secondRow : baseRow, query.page ?? 1),
    );

    render(
      <Wrapper>
        <CommandCenter
          initialData={page(baseRow, 1)}
          initialState={{
            priority: "",
            workflowState: "",
            overdue: "",
            alertStatus: "",
            evidenceStatus: "",
            owner: "",
            sort: "priority",
            direction: "desc",
            page: 1,
            pageSize: 1,
          }}
        />
      </Wrapper>,
    );

    expect(screen.getByText("SYN-R7-001")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Trang sau"));

    await waitFor(() =>
      expect(loadCommandCenterWith).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({ page: 2, page_size: 1 }),
      ),
    );
    expect(await screen.findByText("SYN-R7-002")).toBeInTheDocument();
  });
});
