"use client";

import { useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  MetricTile,
  OfflineState,
  Pagination,
  StaleDataBanner,
} from "@vinami/ui";
import { createBrowserApiClient } from "@web/shared/api/browser";
import { presentError } from "@web/shared/errors/presentation";
import { formatRelative } from "@web/shared/formatting";
import { useConnectivity } from "@web/shared/hooks/use-connectivity";
import { IntegrationStatusPanel } from "@web/features/realtime/integration-status-panel";
import { RealtimeStatus } from "@web/features/realtime/connection-status";
import { useRealtimeUpdates } from "@web/features/realtime/use-realtime-updates";
import { ActiveCaseTable } from "./active-case-table";
import { loadCommandCenterWith } from "./data";
import { FilterBar, type CommandFilters } from "./filter-bar";
import type { CommandCenterPageView } from "./model";
import { SelectedCasePanel } from "./selected-case-panel";

export interface CommandCenterState extends CommandFilters {
  page: number;
  pageSize: number;
  selected?: string;
}

export function CommandCenter({
  initialData,
  initialState,
}: {
  initialData: CommandCenterPageView;
  initialState: CommandCenterState;
}) {
  const online = useConnectivity();
  const [state, setState] = useState(initialState);
  const serverQuery = toServerQuery(state);
  const initialServerQuery = useMemo(
    () => toServerQuery(initialState),
    [initialState],
  );
  const usesInitialQuery = sameQuery(serverQuery, initialServerQuery);
  const realtime = useRealtimeUpdates({
    invalidate: [["r7-command-center"], ["r10-integration-status"]],
  });
  const query = useQuery({
    queryKey: ["r7-command-center", serverQuery],
    queryFn: () => loadCommandCenterWith(createBrowserApiClient(), serverQuery),
    initialData: usesInitialQuery ? initialData : undefined,
    placeholderData: keepPreviousData,
    staleTime: 20_000,
    refetchInterval: 30_000,
  });
  const updateUrl = (next: CommandCenterState) => {
    setState(next);
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries({
      priority: next.priority,
      workflow_state: next.workflowState,
      overdue: next.overdue,
      alert_status: next.alertStatus,
      evidence_status: next.evidenceStatus,
      owner: next.owner.trim(),
      sort: next.sort,
      direction: next.direction,
      page: next.page > 1 ? String(next.page) : "",
      selected: next.selected ?? "",
    })) {
      if (value) params.set(key, value);
    }
    const serialized = params.toString();
    window.history.replaceState(
      null,
      "",
      `/command-center${serialized ? `?${serialized}` : ""}`,
    );
  };
  if (!online && !query.data)
    return <OfflineState onRetry={() => query.refetch()} />;
  if (query.isLoading && !query.data) return <LoadingSkeleton lines={10} />;
  if (query.isError && !query.data) {
    const error = presentError(query.error);
    return (
      <ErrorState
        {...error}
        onRetry={error.retryable ? () => query.refetch() : undefined}
      />
    );
  }
  const data = query.data;
  if (!data) return null;
  const inlineError = query.isError ? presentError(query.error) : null;
  const stale =
    Date.now() - new Date(data.evaluated_at).getTime() > 60_000 || !online;
  const selected = data.items.find((item) => item.case_id === state.selected);
  const summary = data.items.reduce(
    (value, item) => ({
      overdue: value.overdue + (item.overdue_task_count > 0 ? 1 : 0),
      alerts: value.alerts + (item.unresolved_alert_count > 0 ? 1 : 0),
      evidence: value.evidence + (item.evidence_status !== "current" ? 1 : 0),
    }),
    { overdue: 0, alerts: 0, evidence: 0 },
  );
  return (
    <>
      {stale && (
        <StaleDataBanner updatedLabel={formatRelative(data.evaluated_at)} />
      )}
      <RealtimeStatus
        state={realtime.state}
        lastUpdateAt={realtime.lastUpdateAt}
        notification={realtime.notification}
      />
      {inlineError && (
        <div className="vm-banner vm-banner--critical" role="alert">
          <div>
            <strong>Đang dùng dữ liệu điều phối đã lưu tạm</strong>
            <p>{inlineError.description}</p>
          </div>
          {inlineError.retryable && (
            <button
              className="vm-button"
              type="button"
              onClick={() => query.refetch()}
            >
              Thử lại
            </button>
          )}
        </div>
      )}
      <section className="vm-command-summary" aria-label="Tóm tắt điều phối">
        <MetricTile
          label="Ca đang hoạt động"
          value={data.total}
          detail={`Trang ${data.page}`}
        />
        <MetricTile
          label="Ca quá hạn"
          value={summary.overdue}
          detail="Trong trang hiện tại"
        />
        <MetricTile
          label="Ca có cảnh báo"
          value={summary.alerts}
          detail="Chưa xử lý"
        />
        <MetricTile
          label="Cần chú ý bằng chứng"
          value={summary.evidence}
          detail="Thiếu, cũ hoặc giới hạn"
        />
      </section>
      <FilterBar
        value={state}
        onChange={(filters) =>
          updateUrl({ ...state, ...filters, page: 1, selected: undefined })
        }
      />
      <div className="vm-command-layout">
        <section aria-label="Hàng đợi ca đang hoạt động">
          {query.isFetching && (
            <div className="vm-refresh-skeleton">
              <LoadingSkeleton
                lines={3}
                label="Đang làm mới trạng thái điều phối"
              />
            </div>
          )}
          {data.items.length ? (
            <ActiveCaseTable
              rows={data.items}
              referenceTime={data.evaluated_at}
              selectedCaseId={state.selected}
              onSelect={(selectedCase) =>
                updateUrl({ ...state, selected: selectedCase })
              }
            />
          ) : (
            <EmptyState
              title="Không có ca phù hợp với góc nhìn này"
              description="Hãy điều chỉnh bộ lọc. Bằng chứng thiếu không bao giờ được xem là bằng chứng âm tính."
            />
          )}
          <Pagination
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onChange={(page) =>
              updateUrl({ ...state, page, selected: undefined })
            }
          />
        </section>
        <SelectedCasePanel
          row={selected}
          referenceTime={data.evaluated_at}
          onClear={() => updateUrl({ ...state, selected: undefined })}
        />
      </div>
      <IntegrationStatusPanel />
    </>
  );
}

function toServerQuery(state: CommandCenterState) {
  const owner = state.owner.trim();
  return {
    page: state.page,
    page_size: state.pageSize,
    priority: state.priority || undefined,
    workflow_state: state.workflowState || undefined,
    overdue: state.overdue ? state.overdue === "true" : undefined,
    alert_status: state.alertStatus || undefined,
    evidence_status: state.evidenceStatus || undefined,
    owner_id: isUuid(owner) ? owner : undefined,
    sort: state.sort,
    direction: state.direction,
  } as const;
}

function isUuid(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value,
  );
}

function sameQuery(
  first: ReturnType<typeof toServerQuery>,
  second: ReturnType<typeof toServerQuery>,
) {
  const keys = new Set([...Object.keys(first), ...Object.keys(second)]);
  for (const key of keys) {
    const typedKey = key as keyof ReturnType<typeof toServerQuery>;
    if (first[typedKey] !== second[typedKey]) return false;
  }
  return true;
}
