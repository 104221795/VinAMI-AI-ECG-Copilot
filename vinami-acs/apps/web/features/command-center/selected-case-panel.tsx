"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import {
  CalendarClock,
  Clock3,
  ListChecks,
  ShieldAlert,
  UserRoundCheck,
} from "lucide-react";
import {
  Button,
  ClinicalCard,
  EmptyState,
  PriorityBadge,
  StatusBadge,
} from "@vinami/ui";
import {
  formatDueLabel,
  formatDueRelative,
  formatRelative,
  formatTimestamp,
  shortReference,
} from "@web/shared/formatting";
import {
  viAction,
  viClinicalTerm,
  viDecisionType,
  viPriority,
  viStatus,
  viTaskType,
} from "@web/shared/locale/vi";
import { EvidenceAutomationPanel } from "@web/features/evidence/evidence-automation-panel";
import type { CommandCenterCaseView } from "./model";

export function SelectedCasePanel({
  row,
  onClear,
  referenceTime,
}: {
  row?: CommandCenterCaseView;
  onClear: () => void;
  referenceTime: string;
}) {
  if (!row) {
    return (
      <ClinicalCard className="vm-selected-panel">
        <EmptyState
          title="Chưa chọn ca"
          description="Chọn một dòng trong hàng đợi để xem ngữ cảnh điều phối đã lưu."
        />
      </ClinicalCard>
    );
  }

  const now = new Date(referenceTime).getTime();
  const action = nextOperationalAction(row);
  const schedule = scheduleSummary(row, now);

  return (
    <aside
      className="vm-command-quick-view"
      aria-label="Xem nhanh ca đang chọn"
    >
      <ClinicalCard
        className="vm-selected-panel"
        action={<Button onClick={onClear}>Bỏ chọn</Button>}
      >
        <header className="vm-selected-hero">
          <div>
            <p className="vm-eyebrow">Ca đang chọn</p>
            <h2>{row.patient_reference}</h2>
            <p className="vm-selected-reference">
              <strong>{shortReference(row.case_id, "CASE")}</strong>
              <code>{row.case_id}</code>
            </p>
          </div>
          <div className="vm-selected-badges">
            <PriorityBadge priority={row.operational_priority} />
            <StatusBadge status={row.workflow_state ?? row.case_status} />
          </div>
        </header>

        <section
          className={`vm-next-action vm-next-action--${action.tone}`}
          aria-label="Hành động điều phối tiếp theo"
        >
          {action.tone === "critical" ? (
            <ShieldAlert size={18} aria-hidden="true" />
          ) : (
            <Clock3 size={18} aria-hidden="true" />
          )}
          <div>
            <strong>{action.title}</strong>
            <p>{action.detail}</p>
          </div>
        </section>

        <div className="vm-quick-facts" aria-label="Thông tin nhanh của ca">
          <QuickFact label="Vị trí" value={row.location} />
          <QuickFact
            label="Đã mở"
            value={formatRelative(row.opened_at, now)}
            title={formatTimestamp(row.opened_at)}
          />
          <QuickFact
            label="Hoạt động gần nhất"
            value={formatRelative(row.latest_activity_at, now)}
            title={formatTimestamp(row.latest_activity_at)}
          />
          <QuickFact label="Phụ trách" value={ownerLabel(row)} />
        </div>

        <section className="vm-quick-section">
          <h3>Quyết định của bác sĩ</h3>
          {row.decision_id ? (
            <article className="vm-authority-card">
              <UserRoundCheck size={17} aria-hidden="true" />
              <div>
                <strong>
                  {viDecisionType(row.decision_type ?? "documented_decision")}
                </strong>
                <p>{row.decision_rationale}</p>
                <small>
                  Bản ghi hiện hành đã lưu |{" "}
                  {shortReference(row.decision_id, "DEC")}
                </small>
              </div>
            </article>
          ) : (
            <p>Chưa có quyết định hiện hành của bác sĩ được lưu.</p>
          )}
        </section>

        <section className="vm-quick-section">
          <EvidenceAutomationPanel
            automation={row.automation}
            compact
            showAlertDigest
          />
        </section>

        <section className="vm-quick-section">
          <h3>Lịch điều phối</h3>
          <div className="vm-schedule-card">
            <CalendarClock size={17} aria-hidden="true" />
            <div>
              <strong>{schedule.title}</strong>
              <p>{schedule.detail}</p>
              <small>{formatDueLabel(row.next_due_at)}</small>
            </div>
          </div>
        </section>

        <section className="vm-quick-section">
          <h3>Công việc đang mở</h3>
          {row.tasks.length === 0 ? (
            <p>Không có công việc điều phối đang mở.</p>
          ) : (
            <ul className="vm-compact-list">
              {row.tasks.slice(0, 4).map((task) => (
                <li key={task.task_id}>
                  <span>
                    <strong>{viTaskType(task.task_type)}</strong>
                    <small>
                      {viStatus(task.status)} | {viPriority(task.priority)}
                    </small>
                  </span>
                  <span>{formatDueRelative(task.due_at, now)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="vm-quick-section">
          <h3>Cảnh báo chưa xử lý</h3>
          {row.alerts.length === 0 ? (
            <p>Không có cảnh báo điều phối chưa xử lý.</p>
          ) : (
            <ul className="vm-compact-list">
              {row.alerts.slice(0, 4).map((alert) => (
                <li key={alert.alert_id}>
                  <span>
                    <strong>{viClinicalTerm(alert.alert_type)}</strong>
                    <small>
                      {viStatus(alert.status)} | mức leo thang{" "}
                      {alert.escalation_level}
                    </small>
                  </span>
                  <StatusBadge status={alert.severity} />
                </li>
              ))}
            </ul>
          )}
        </section>

        <nav
          className="vm-workspace-links"
          aria-label="Không gian làm việc của ca đang chọn"
        >
          <WorkspaceLink href={`/cases/${row.case_id}/documentation`}>
            Tiếp nhận / Sinh hiệu
          </WorkspaceLink>
          <WorkspaceLink href={`/cases/${row.case_id}/clinical-reasoning`}>
            Tổng hợp lâm sàng
          </WorkspaceLink>
          <WorkspaceLink href={`/cases/${row.case_id}/ecg`}>ECG</WorkspaceLink>
          <WorkspaceLink href={`/cases/${row.case_id}/troponin`}>
            Troponin
          </WorkspaceLink>
          <WorkspaceLink href={`/cases/${row.case_id}/workflow`}>
            Quy trình
          </WorkspaceLink>
          <WorkspaceLink href={`/cases/${row.case_id}/timeline`}>
            Dòng thời gian
          </WorkspaceLink>
          <WorkspaceLink href={`/cases/${row.case_id}/audit`}>
            Nhật ký kiểm chứng
          </WorkspaceLink>
        </nav>

        <p className="vm-safety-note">
          Chỉ là tổng quan điều phối. Đầu ra AI không quyết định ưu tiên hoặc
          thẩm quyền lâm sàng.
        </p>
      </ClinicalCard>
    </aside>
  );
}

function QuickFact({
  label,
  value,
  title,
}: {
  label: string;
  value: string;
  title?: string;
}) {
  return (
    <span title={title}>
      <small>{label}</small>
      <strong>{value}</strong>
    </span>
  );
}

function ownerLabel(row: CommandCenterCaseView) {
  if (row.owner_user_id) return shortReference(row.owner_user_id, "USR");
  if (row.owner_team_id) return shortReference(row.owner_team_id, "TEAM");
  return "Chưa phân công";
}

function nextOperationalAction(row: CommandCenterCaseView) {
  const hasCriticalSignal =
    row.operational_priority === "critical" ||
    row.alerts.some((alert) => alert.severity === "critical") ||
    row.decision_type === "request_cath_lab_review";
  if (hasCriticalSignal) {
    return {
      tone: "critical" as const,
      title: "Cần rà soát ngay theo chỉ đạo bác sĩ",
      detail:
        "Dùng không gian Quy trình để xử lý công việc, cảnh báo và rà soát đã được bác sĩ xác nhận. Dashboard không tự kích hoạt bất kỳ hướng xử trí nào.",
    };
  }
  if (row.overdue_task_count > 0) {
    return {
      tone: "warning" as const,
      title: "Có công việc điều phối quá hạn",
      detail:
        "Ít nhất một công việc đã lưu đang quá hạn. Rà soát người phụ trách và mức leo thang trước khi dựa vào tóm tắt ca.",
    };
  }
  if (row.next_due_at) {
    return {
      tone: "scheduled" as const,
      title: "Có việc đã lên hạn đang chờ",
      detail:
        "Hạn tiếp theo đến từ quy trình hoặc nhắc việc backend, không phải từ luật tự tính trên frontend.",
    };
  }
  return {
    tone: "neutral" as const,
    title: "Chưa có việc đến hạn",
    detail:
      "Tiếp tục rà soát bằng chứng và quyết định do bác sĩ ghi nhận trong các không gian phụ trách.",
  };
}

function scheduleSummary(row: CommandCenterCaseView, now: number) {
  if (row.operational_priority === "critical") {
    return {
      title: "Rà soát ngay, không phải lịch thường quy",
      detail:
        "Trạng thái khẩn cấp cần được xử lý qua công việc, cảnh báo và quyết định bác sĩ đã lưu.",
    };
  }
  if (row.next_due_at) {
    return {
      title: `Hạn tiếp theo ${formatDueRelative(row.next_due_at, now)}`,
      detail:
        row.tasks[0]?.task_type !== undefined
          ? `Công việc hiện tại: ${viTaskType(row.tasks[0].task_type)}`
          : "Một nhắc việc hoặc bộ đếm quy trình đã lưu đang đến hạn.",
    };
  }
  return {
    title: "MVP chưa có lịch hẹn bệnh viện",
    detail:
      "MVP hiện chỉ đặt hạn cho bằng chứng lặp lại và công việc điều phối. Lịch hẹn bệnh viện thuộc phạm vi tích hợp sau.",
  };
}

function WorkspaceLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return <Link href={href}>{children}</Link>;
}
