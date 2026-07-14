"use client";

import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { useMemo } from "react";
import {
  PriorityBadge,
  StatusBadge,
  TechnicalDetailsDisclosure,
} from "@vinami/ui";
import type { CaseQueueRowView } from "@web/entities/clinical-case/model";
import { formatRelative, formatTimestamp } from "@web/shared/formatting";

export function ActiveCaseTable({
  rows,
  selectedCaseId,
  onSelect,
  referenceTime,
}: {
  rows: CaseQueueRowView[];
  selectedCaseId?: string;
  onSelect: (caseId: string) => void;
  referenceTime?: string;
}) {
  const now = referenceTime ? new Date(referenceTime).getTime() : Date.now();
  const columns = useMemo<ColumnDef<CaseQueueRowView>[]>(
    () => [
      {
        header: "Priority",
        accessorKey: "priority",
        cell: ({ row }) => <PriorityBadge priority={row.original.priority} />,
      },
      {
        header: "Patient",
        accessorKey: "patientReference",
        cell: ({ row }) => (
          <span className="vm-cell-primary">
            {row.original.patientReference}
            <small>{row.original.demographics}</small>
          </span>
        ),
      },
      { header: "Location", accessorKey: "location" },
      {
        header: "Case status",
        accessorKey: "status",
        cell: ({ row }) => <StatusBadge status={row.original.status} />,
      },
      {
        header: "Case reference",
        accessorKey: "caseReference",
        cell: ({ row }) => (
          <span className="vm-cell-primary">
            {row.original.caseReference}
            <small>{row.original.encounterReference}</small>
          </span>
        ),
      },
      {
        header: "Opened",
        accessorKey: "openedAt",
        cell: ({ row }) => (
          <span
            title={formatTimestamp(row.original.openedAt)}
            className="vm-tabular"
          >
            {formatRelative(row.original.openedAt, now)}
          </span>
        ),
      },
      {
        header: "Last updated",
        accessorKey: "updatedAt",
        cell: ({ row }) => (
          <span
            title={formatTimestamp(row.original.updatedAt)}
            className="vm-tabular"
          >
            {formatRelative(row.original.updatedAt, now)}
          </span>
        ),
      },
      {
        id: "technical",
        header: "",
        cell: ({ row }) => (
          <TechnicalDetailsDisclosure title="Version">
            <code>v{row.original.aggregateVersion}</code>
          </TechnicalDetailsDisclosure>
        ),
      },
    ],
    [now],
  );
  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });
  return (
    <div className="vm-table-wrap">
      <table className="vm-table" aria-label="Active suspected ACS cases">
        <thead>
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id}>
              {group.headers.map((header) => (
                <th key={header.id} scope="col">
                  {flexRender(
                    header.column.columnDef.header,
                    header.getContext(),
                  )}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              tabIndex={0}
              aria-selected={row.original.caseId === selectedCaseId}
              onClick={() => onSelect(row.original.caseId)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(row.original.caseId);
                }
              }}
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
