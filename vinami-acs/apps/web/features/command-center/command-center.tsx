"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  MetricTile,
  OfflineState,
  Pagination,
  StaleDataBanner,
} from "@vinami/ui";
import type { CaseQueueView } from "@web/entities/clinical-case/model";
import { loadCaseQueueWith } from "./data";
import { ActiveCaseTable } from "./active-case-table";
import { FilterBar, type CommandFilters } from "./filter-bar";
import { SelectedCasePanel } from "./selected-case-panel";
import { createBrowserApiClient } from "@web/shared/api/browser";
import { presentError } from "@web/shared/errors/presentation";
import { formatRelative } from "@web/shared/formatting";
import { useConnectivity } from "@web/shared/hooks/use-connectivity";

export interface CommandCenterState extends CommandFilters {
  page: number;
  pageSize: number;
  selected?: string;
}

export function CommandCenter({
  initialData,
  initialState,
}: {
  initialData: CaseQueueView;
  initialState: CommandCenterState;
}) {
  const online = useConnectivity();
  const [state, setState] = useState(initialState);
  const serverQuery = {
    page: state.page,
    page_size: state.pageSize,
    status: state.status || undefined,
    priority: state.priority || undefined,
    location: state.location || undefined,
  };
  const isInitialQuery =
    state.page === initialState.page &&
    state.status === initialState.status &&
    state.priority === initialState.priority &&
    state.location === initialState.location;
  const query = useQuery({
    queryKey: ["clinical-cases", serverQuery],
    queryFn: () => loadCaseQueueWith(createBrowserApiClient(), serverQuery),
    initialData: isInitialQuery ? initialData : undefined,
    staleTime: 30_000,
  });
  const updateUrl = (next: CommandCenterState) => {
    setState(next);
    const params = new URLSearchParams();
    if (next.status) params.set("status", next.status);
    if (next.priority) params.set("priority", next.priority);
    if (next.location) params.set("location", next.location);
    if (next.search) params.set("q", next.search);
    if (next.page > 1) params.set("page", String(next.page));
    if (next.selected) params.set("selected", next.selected);
    const serialized = params.toString();
    window.history.replaceState(
      null,
      "",
      `/command-center${serialized ? `?${serialized}` : ""}`,
    );
  };
  const rows = useMemo(() => {
    const search = state.search.trim().toLowerCase();
    if (!search) return query.data?.rows ?? [];
    return (query.data?.rows ?? []).filter((row) =>
      [row.patientReference, row.caseReference, row.encounterReference].some(
        (value) => value.toLowerCase().includes(search),
      ),
    );
  }, [query.data?.rows, state.search]);
  const selectedRow = query.data?.rows.find(
    (row) => row.caseId === state.selected,
  );
  if (!online && !query.data)
    return <OfflineState onRetry={() => query.refetch()} />;
  if (query.isLoading) return <LoadingSkeleton lines={9} />;
  if (query.isError) {
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
  const stale =
    Date.now() - new Date(data.refreshedAt).getTime() > 60_000 || !online;
  return (
    <>
      {stale && (
        <StaleDataBanner updatedLabel={formatRelative(data.refreshedAt)} />
      )}
      {data.partialCount > 0 && (
        <div className="vm-banner vm-banner--stale" role="status">
          {data.partialCount} case row could not load its Patient or Encounter
          projection.
        </div>
      )}
      <div className="vm-layout-split">
        <section aria-label="Active case queue">
          <div style={{ display: "flex", gap: 1, marginBottom: 12 }}>
            <MetricTile
              label="Active cases"
              value={data.total}
              detail={`Page ${data.page}`}
            />
            <MetricTile
              label="Data state"
              value={query.isFetching ? "Refreshing" : "Current"}
              detail={`Updated ${formatRelative(data.refreshedAt, new Date(data.refreshedAt).getTime())}`}
            />
          </div>
          <FilterBar
            value={state}
            locations={[
              ...new Set(data.rows.map((row) => row.location)),
            ].sort()}
            onChange={(filters) => updateUrl({ ...state, ...filters, page: 1 })}
          />
          {rows.length ? (
            <ActiveCaseTable
              rows={rows}
              referenceTime={data.refreshedAt}
              selectedCaseId={state.selected}
              onSelect={(selected) => updateUrl({ ...state, selected })}
            />
          ) : (
            <EmptyState
              title="No cases match this view"
              description="Adjust filters or search. No case records have been fabricated for this state."
            />
          )}
          <Pagination
            page={data.page}
            pageSize={data.pageSize}
            total={data.total}
            onChange={(page) => updateUrl({ ...state, page })}
          />
        </section>
        <SelectedCasePanel
          row={selectedRow}
          referenceTime={data.refreshedAt}
          onClear={() => updateUrl({ ...state, selected: undefined })}
        />
      </div>
    </>
  );
}
