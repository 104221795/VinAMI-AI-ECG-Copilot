import Link from "next/link";
import type { ReactNode } from "react";
import {
  PriorityBadge,
  StatusBadge,
  TechnicalDetailsDisclosure,
} from "@vinami/ui";
import type { CaseWorkspaceView } from "@web/entities/clinical-case/model";
import { formatTimestamp } from "@web/shared/formatting";
import { viWorkflowState } from "@web/shared/locale/vi";

type CaseWorkspaceSection =
  | "overview"
  | "documentation"
  | "ecg"
  | "troponin"
  | "clinical-reasoning"
  | "workflow"
  | "timeline"
  | "audit";

export function CaseWorkspaceHeader({
  value,
  active = "overview",
  workflowStatus,
}: {
  value: CaseWorkspaceView;
  active?: CaseWorkspaceSection;
  workflowStatus?: string;
}) {
  return (
    <div className="vm-card vm-case-context">
      <div className="vm-card__body">
        <nav aria-label="Đường dẫn" className="vm-breadcrumb">
          <Link href="/command-center">Trung tâm điều phối</Link> /{" "}
          <span aria-current="page">{value.caseReference}</span>
        </nav>
        <div className="vm-page-header vm-case-context__header">
          <div>
            <p className="vm-eyebrow">Ca nghi hội chứng mạch vành cấp</p>
            <h1 className="vm-case-context__title" title={value.caseId}>
              {value.caseReference}
            </h1>
            <p className="vm-case-context__meta">
              <span>Bệnh nhân {value.patientReference}</span>
              <span>{value.demographics}</span>
              <span>{value.location}</span>
              <span>{value.encounterReference}</span>
              <span>
                Quy trình:{" "}
                {workflowStatus
                  ? viWorkflowState(workflowStatus)
                  : "Chưa ghi nhận"}
              </span>
            </p>
          </div>
          <div className="vm-case-header">
            <PriorityBadge priority={value.priority} />
            <StatusBadge status={value.status} />
          </div>
        </div>
        <nav className="vm-case-sections" aria-label="Các khu vực của ca">
          <WorkspaceNavLink
            active={active === "overview"}
            href={`/cases/${value.caseId}`}
          >
            Tổng quan
          </WorkspaceNavLink>
          <WorkspaceNavLink
            active={active === "documentation"}
            href={`/cases/${value.caseId}/documentation`}
          >
            Tiếp nhận / Sinh hiệu
          </WorkspaceNavLink>
          <WorkspaceNavLink
            active={active === "ecg"}
            href={`/cases/${value.caseId}/ecg`}
          >
            ECG
          </WorkspaceNavLink>
          <WorkspaceNavLink
            active={active === "troponin"}
            href={`/cases/${value.caseId}/troponin`}
          >
            Troponin
          </WorkspaceNavLink>
          <WorkspaceNavLink
            active={active === "clinical-reasoning"}
            href={`/cases/${value.caseId}/clinical-reasoning`}
          >
            Tổng hợp lâm sàng
          </WorkspaceNavLink>
          <WorkspaceNavLink
            active={active === "workflow"}
            href={`/cases/${value.caseId}/workflow`}
          >
            Quy trình
          </WorkspaceNavLink>
          <WorkspaceNavLink
            active={active === "timeline"}
            href={`/cases/${value.caseId}/timeline`}
          >
            Dòng thời gian
          </WorkspaceNavLink>
          <WorkspaceNavLink
            active={active === "audit"}
            href={`/cases/${value.caseId}/audit`}
          >
            Nhật ký kiểm chứng
          </WorkspaceNavLink>
          <TechnicalDetailsDisclosure title="Tham chiếu kỹ thuật của ca">
            <dl>
              <dt>UUID ca</dt>
              <dd>
                <code>{value.caseId}</code>
              </dd>
              <dt>Mã bệnh nhân</dt>
              <dd>
                <code>{value.patientReference}</code>
              </dd>
              <dt>Phiên bản aggregate</dt>
              <dd>v{value.aggregateVersion}</dd>
              <dt>Cập nhật gần nhất</dt>
              <dd>{formatTimestamp(value.updatedAt)}</dd>
            </dl>
          </TechnicalDetailsDisclosure>
        </nav>
      </div>
    </div>
  );
}

function WorkspaceNavLink({
  active,
  href,
  children,
}: {
  active: boolean;
  href: string;
  children: ReactNode;
}) {
  return (
    <Link
      className={`vm-case-tab${active ? " vm-case-tab--active" : ""}`}
      href={href}
      aria-current={active ? "page" : undefined}
    >
      {children}
    </Link>
  );
}
