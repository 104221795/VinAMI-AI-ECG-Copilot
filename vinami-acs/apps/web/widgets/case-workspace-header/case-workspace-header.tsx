import Link from "next/link";
import {
  PriorityBadge,
  StatusBadge,
  TechnicalDetailsDisclosure,
} from "@vinami/ui";
import type { CaseWorkspaceView } from "@web/entities/clinical-case/model";
import { formatTimestamp } from "@web/shared/formatting";

export function CaseWorkspaceHeader({
  value,
  active = "overview",
}: {
  value: CaseWorkspaceView;
  active?:
    | "overview"
    | "ecg"
    | "troponin"
    | "clinical-reasoning"
    | "workflow"
    | "timeline"
    | "audit";
}) {
  return (
    <div className="vm-card" style={{ marginBottom: 18 }}>
      <div className="vm-card__body">
        <nav aria-label="Breadcrumb" style={{ marginBottom: 10 }}>
          <Link href="/command-center">Command Center</Link> /{" "}
          <span aria-current="page">{value.caseReference}</span>
        </nav>
        <div className="vm-page-header" style={{ marginBottom: 12 }}>
          <div>
            <p className="vm-eyebrow">Suspected ACS clinical case</p>
            <h1>{value.patientReference}</h1>
            <p>
              {value.demographics} · {value.location} ·{" "}
              {value.encounterReference}
            </p>
          </div>
          <div className="vm-case-header">
            <PriorityBadge priority={value.priority} />
            <StatusBadge status={value.status} />
          </div>
        </div>
        <nav className="vm-case-header" aria-label="Case workspace sections">
          <Link
            className={`vm-button${active === "workflow" ? " vm-button--primary" : ""}`}
            href={`/cases/${value.caseId}/workflow`}
          >
            Workflow
          </Link>
          <Link
            className={`vm-button${active === "clinical-reasoning" ? " vm-button--primary" : ""}`}
            href={`/cases/${value.caseId}/clinical-reasoning`}
          >
            Clinical Reasoning
          </Link>
          <Link
            className={`vm-button${active === "troponin" ? " vm-button--primary" : ""}`}
            href={`/cases/${value.caseId}/troponin`}
          >
            Troponin
          </Link>
          <Link
            className={`vm-button${active === "ecg" ? " vm-button--primary" : ""}`}
            href={`/cases/${value.caseId}/ecg`}
          >
            ECG
          </Link>
          <Link
            className={`vm-button${active === "overview" ? " vm-button--primary" : ""}`}
            href={`/cases/${value.caseId}`}
          >
            Overview
          </Link>
          <Link
            className={`vm-button${active === "timeline" ? " vm-button--primary" : ""}`}
            href={`/cases/${value.caseId}/timeline`}
          >
            Timeline
          </Link>
          <Link
            className={`vm-button${active === "audit" ? " vm-button--primary" : ""}`}
            href={`/cases/${value.caseId}/audit`}
          >
            Audit
          </Link>
          <TechnicalDetailsDisclosure title="Case technical reference">
            <dl>
              <dt>Case UUID</dt>
              <dd>
                <code>{value.caseId}</code>
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
