"use client";

import { PriorityBadge, StatusBadge } from "@vinami/ui";
import {
  formatDueLabel,
  formatDueRelative,
  shortReference,
} from "@web/shared/formatting";
import { viClinicalTerm } from "@web/shared/locale/vi";
import type { CommandCenterCaseView } from "./model";

export function ActiveCaseTable({
  rows,
  selectedCaseId,
  onSelect,
  referenceTime,
}: {
  rows: CommandCenterCaseView[];
  selectedCaseId?: string;
  onSelect: (caseId: string) => void;
  referenceTime: string;
}) {
  const now = new Date(referenceTime).getTime();
  return (
    <div className="vm-table-wrap vm-command-table-wrap">
      <table
        className="vm-table vm-command-table"
        aria-label="Hàng đợi điều phối ca nghi hội chứng mạch vành cấp"
      >
        <thead>
          <tr>
            <th scope="col">Ưu tiên</th>
            <th scope="col">Bệnh nhân / ca</th>
            <th scope="col">Quy trình</th>
            <th scope="col">Bằng chứng</th>
            <th scope="col">Công việc</th>
            <th scope="col">Cảnh báo</th>
            <th scope="col">Hạn tiếp theo</th>
            <th scope="col">Phụ trách</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.case_id}
              tabIndex={0}
              aria-selected={row.case_id === selectedCaseId}
              onClick={() => onSelect(row.case_id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(row.case_id);
                }
              }}
            >
              <td data-label="Ưu tiên">
                <PriorityBadge priority={row.operational_priority} />
                {priorityDetail(row) && (
                  <small className="vm-cell-note">{priorityDetail(row)}</small>
                )}
              </td>
              <td data-label="Bệnh nhân / ca">
                <span className="vm-cell-primary">
                  {row.patient_reference}
                  <small>
                    {shortReference(row.case_id, "CASE")} | {row.location}
                  </small>
                </span>
              </td>
              <td data-label="Quy trình">
                <StatusBadge status={row.workflow_state ?? row.case_status} />
              </td>
              <td data-label="Bằng chứng">
                <StatusBadge status={row.evidence_status} />
              </td>
              <td data-label="Công việc">
                <strong className="vm-tabular">{row.active_task_count}</strong>
                {row.overdue_task_count > 0 && (
                  <small className="vm-cell-note vm-text-urgent">
                    {row.overdue_task_count} quá hạn
                  </small>
                )}
              </td>
              <td data-label="Cảnh báo">
                <strong className="vm-tabular">
                  {row.unresolved_alert_count}
                </strong>
              </td>
              <td className="vm-date-cell" data-label="Hạn tiếp theo">
                <span title={formatDueLabel(row.next_due_at)}>
                  {formatDueRelative(row.next_due_at, now)}
                </span>
              </td>
              <td data-label="Phụ trách">{ownerLabel(row)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ownerLabel(row: CommandCenterCaseView) {
  if (row.owner_user_id) return shortReference(row.owner_user_id, "USR");
  if (row.owner_team_id) return shortReference(row.owner_team_id, "TEAM");
  return "Chưa phân công";
}

function priorityDetail(row: CommandCenterCaseView) {
  const reason = row.priority_reason.trim();
  const normalized = reason.toLowerCase();
  const priority = row.operational_priority.toLowerCase();
  if (!reason) return null;
  if (
    normalized === `${priority} priority` ||
    normalized === `unresolved ${priority} operational alert`
  ) {
    return null;
  }
  return translatePriorityReason(reason);
}

function translatePriorityReason(reason: string) {
  const normalized = reason.toLowerCase();
  if (normalized.includes("human-recorded")) {
    return "Ưu tiên do người dùng lâm sàng ghi nhận";
  }
  if (normalized.includes("unresolved") && normalized.includes("alert")) {
    return "Có cảnh báo điều phối chưa xử lý";
  }
  if (normalized.includes("overdue")) return "Có công việc quá hạn";
  if (normalized.includes("missing") || normalized.includes("evidence")) {
    return "Cần rà soát bằng chứng";
  }
  return viClinicalTerm(reason);
}
