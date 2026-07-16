import Link from "next/link";
import type { ReactNode } from "react";
import {
  PriorityBadge,
  StatusBadge,
  TechnicalDetailsDisclosure,
} from "@vinami/ui";
import type { CaseWorkspaceView } from "@web/entities/clinical-case/model";
import { formatTimestamp, shortReference } from "@web/shared/formatting";

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
        <nav aria-label="Breadcrumb" className="vm-breadcrumb">
          <Link href="/command-center">Command Center</Link> /{" "}
          <span aria-current="page">{value.caseReference}</span>
        </nav>
        <div className="vm-page-header vm-case-context__header">
          <div>
            <p className="vm-eyebrow">Suspected ACS clinical case</p>
            <h1
              className="vm-case-context__title"
              title={value.patientReference}
            >
              {value.patientReference}
            </h1>
            <p className="vm-case-context__meta">
              <span>{value.demographics}</span>
              <span>{value.location}</span>
              <span>{value.encounterReference}</span>
              <span>{shortReference(value.caseId, "CASE")}</span>
              <span>
                Workflow:{" "}
                {workflowStatus ? formatLabel(workflowStatus) : "open source"}
              </span>
            </p>
          </div>
          <div className="vm-case-header">
            <PriorityBadge priority={value.priority} />
            <StatusBadge status={value.status} />
          </div>
        </div>
        <nav
          className="vm-case-header vm-case-sections"
          aria-label="Case workspace sections"
        >
          <WorkspaceNavLink
            active={active === "overview"}
            href={`/cases/${value.caseId}`}
          >
            Overview
          </WorkspaceNavLink>
          <WorkspaceNavLink
            active={active === "documentation"}
            href={`/cases/${value.caseId}/documentation`}
          >
            Triage / Vitals
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
            Clinical Reasoning
          </WorkspaceNavLink>
          <WorkspaceNavLink
            active={active === "workflow"}
            href={`/cases/${value.caseId}/workflow`}
          >
            Workflow
          </WorkspaceNavLink>
          <WorkspaceNavLink
            active={active === "timeline"}
            href={`/cases/${value.caseId}/timeline`}
          >
            Timeline
          </WorkspaceNavLink>
          <WorkspaceNavLink
            active={active === "audit"}
            href={`/cases/${value.caseId}/audit`}
          >
            Audit
          </WorkspaceNavLink>
          <TechnicalDetailsDisclosure title="Case technical reference">
            <dl>
              <dt>Case UUID</dt>
              <dd>
                <code>{value.caseId}</code>
              </dd>
              <dt>Patient reference</dt>
              <dd>
                <code>{value.patientReference}</code>
              </dd>
              <dt>Aggregate version</dt>
              <dd>v{value.aggregateVersion}</dd>
              <dt>Last update</dt>
              <dd>{formatTimestamp(value.updatedAt)}</dd>
            </dl>
          </TechnicalDetailsDisclosure>
        </nav>
      </div>
    </div>
  );
}

function formatLabel(value: string) {
  return value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
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
      className={`vm-button${active ? " vm-button--primary" : ""}`}
      href={href}
    >
      {children}
    </Link>
  );
}
