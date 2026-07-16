"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { AlertTriangle, CheckCircle2, Clock3, FilePenLine } from "lucide-react";
import { createBrowserApiClient } from "@web/shared/api/browser";
import { formatTimestamp } from "@web/shared/formatting";
import {
  clinicalReasoningWorkspaceSchema,
  type AssessmentView,
  type ClinicalReasoningWorkspaceView,
  type DecisionView,
} from "./model";

const decisionLabels = {
  continue_observation: "Continue observation",
  request_repeat_ecg: "Request repeat ECG",
  request_repeat_troponin: "Request repeat troponin",
  request_additional_information: "Request additional information",
  request_cardiology_review: "Request cardiology review",
  request_cath_lab_review: "Physician request for cath-lab review",
  maintain_current_plan: "Maintain current plan",
  other_documented_plan: "Other documented plan",
} as const;
type DecisionCode = keyof typeof decisionLabels;

type AssessmentForm = {
  summary: string;
  uncertainty: string;
  additionalInformation: string;
  correctionReason: string;
};
type DecisionForm = {
  decisionType: DecisionCode;
  rationale: string;
  uncertainty: string;
  correctionReason: string;
};

export function ClinicalReasoningWorkspace({
  caseId,
  initialValue,
}: {
  caseId: string;
  initialValue: ClinicalReasoningWorkspaceView;
}) {
  const api = useMemo(() => createBrowserApiClient(), []);
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["clinical-reasoning", caseId],
    initialData: initialValue,
    queryFn: async () =>
      clinicalReasoningWorkspaceSchema.parse(
        await api.getClinicalReasoningWorkspace(caseId),
      ),
  });
  const value = query.data;
  const snapshot = value.snapshot;
  const [supporting, setSupporting] = useState<string[]>([]);
  const [contradictory, setContradictory] = useState<string[]>([]);
  const [assessmentCorrection, setAssessmentCorrection] =
    useState<AssessmentView | null>(null);
  const [decisionCorrection, setDecisionCorrection] =
    useState<DecisionView | null>(null);
  const [pendingDecision, setPendingDecision] = useState<DecisionForm | null>(
    null,
  );
  const [revokeDecision, setRevokeDecision] = useState<DecisionView | null>(
    null,
  );
  const [revocationReason, setRevocationReason] = useState("");
  const assessmentForm = useForm<AssessmentForm>();
  const decisionForm = useForm<DecisionForm>({
    defaultValues: { decisionType: "continue_observation" },
  });
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["clinical-reasoning", caseId] });

  const snapshotMutation = useMutation({
    mutationFn: () =>
      api.createEvidenceSnapshot(
        caseId,
        { expected_case_version: value.case_version },
        crypto.randomUUID(),
      ),
    onSuccess: refresh,
  });
  const assessmentMutation = useMutation({
    mutationFn: async (form: AssessmentForm) => {
      if (!snapshot)
        throw new Error("Create a current evidence snapshot first.");
      const base = {
        snapshot_id: snapshot.snapshot_id,
        expected_snapshot_version: snapshot.record_version,
        summary: form.summary,
        supporting_evidence: supporting,
        contradictory_evidence: contradictory,
        uncertainty: form.uncertainty,
        additional_information_required: form.additionalInformation || null,
      };
      if (assessmentCorrection) {
        return api.correctClinicalAssessment(
          caseId,
          assessmentCorrection.assessment_id,
          {
            ...base,
            expected_assessment_version: assessmentCorrection.record_version,
            correction_reason: form.correctionReason,
          },
          crypto.randomUUID(),
        );
      }
      return api.recordClinicalAssessment(caseId, base, crypto.randomUUID());
    },
    onSuccess: () => {
      assessmentForm.reset();
      setAssessmentCorrection(null);
      refresh();
    },
  });
  const decisionMutation = useMutation({
    mutationFn: async (form: DecisionForm) => {
      if (!snapshot || !value.assessments[0])
        throw new Error(
          "A current snapshot and physician assessment are required.",
        );
      const assessment = value.assessments[0];
      const base = {
        snapshot_id: snapshot.snapshot_id,
        assessment_id: assessment.assessment_id,
        expected_snapshot_version: snapshot.record_version,
        expected_assessment_version: assessment.record_version,
        decision_type: form.decisionType,
        rationale: form.rationale,
        uncertainty: form.uncertainty,
        evidence_references: [...supporting, ...contradictory],
      };
      if (decisionCorrection) {
        return api.correctClinicalDecision(
          caseId,
          decisionCorrection.decision_id,
          {
            ...base,
            expected_decision_version: decisionCorrection.record_version,
            correction_reason: form.correctionReason,
          },
          crypto.randomUUID(),
        );
      }
      return api.recordClinicalDecision(caseId, base, crypto.randomUUID());
    },
    onSuccess: () => {
      setPendingDecision(null);
      setDecisionCorrection(null);
      decisionForm.reset({ decisionType: "continue_observation" });
      refresh();
    },
  });
  const revokeMutation = useMutation({
    mutationFn: async () => {
      if (!snapshot || !revokeDecision)
        throw new Error(
          "A current decision and evidence snapshot are required.",
        );
      const assessment = value.assessments.find(
        (item) => item.assessment_id === revokeDecision.assessment_id,
      );
      if (!assessment)
        throw new Error("Linked physician assessment is unavailable.");
      return api.revokeClinicalDecision(
        caseId,
        revokeDecision.decision_id,
        {
          snapshot_id: snapshot.snapshot_id,
          assessment_id: assessment.assessment_id,
          expected_snapshot_version: snapshot.record_version,
          expected_assessment_version: assessment.record_version,
          expected_decision_version: revokeDecision.record_version,
          decision_type: revokeDecision.decision_type as DecisionCode,
          rationale: revokeDecision.rationale,
          uncertainty: revokeDecision.uncertainty,
          evidence_references: revokeDecision.evidence_references,
          revocation_reason: revocationReason,
          operation: "revoke",
        },
        crypto.randomUUID(),
      );
    },
    onSuccess: () => {
      setRevokeDecision(null);
      setRevocationReason("");
      refresh();
    },
  });

  const sourceOptions = snapshot?.sources ?? [];
  return (
    <main className="vm-reasoning-workspace">
      <section
        className="vm-card vm-reasoning-hero"
        aria-labelledby="reasoning-title"
      >
        <div className="vm-card__body">
          <div>
            <p className="vm-eyebrow">
              Physician workspace - research-use prototype
            </p>
            <h2 id="reasoning-title">Clinical evidence synthesis</h2>
            <p>{value.safety_notice}</p>
          </div>
          <button
            className="vm-button vm-button--primary"
            disabled={snapshotMutation.isPending}
            onClick={() => snapshotMutation.mutate()}
          >
            {snapshotMutation.isPending
              ? "Creating snapshot..."
              : "Create current snapshot"}
          </button>
        </div>
      </section>

      <div className="vm-reasoning-grid">
        <section className="vm-card">
          <div className="vm-card__body">
            <h3>Case identity and evidence freshness</h3>
            <dl className="vm-reasoning-facts">
              <dt>Case</dt>
              <dd>
                <code>{caseId}</code>
              </dd>
              <dt>Case version</dt>
              <dd>v{value.case_version}</dd>
              <dt>Snapshot</dt>
              <dd>
                {snapshot
                  ? `v${snapshot.record_version} - ${formatTimestamp(snapshot.created_at)}`
                  : "Not created"}
              </dd>
            </dl>
            {snapshot &&
              Object.entries(snapshot.freshness).map(([name, status]) => (
                <span
                  className={`vm-evidence-status vm-evidence-status--${status}`}
                  key={name}
                >
                  <Clock3 size={14} /> {name}: {status}
                </span>
              ))}
          </div>
        </section>
        <section className="vm-card">
          <div className="vm-card__body">
            <h3>Evidence limitations</h3>
            {!snapshot && (
              <p>Create a snapshot to inspect persisted evidence.</p>
            )}
            {snapshot &&
              snapshot.missing_evidence.length === 0 &&
              snapshot.technical_conflicts.length === 0 && (
                <p className="vm-positive">
                  <CheckCircle2 size={16} /> No technical gap recorded in this
                  snapshot.
                </p>
              )}
            {snapshot?.missing_evidence.map((item) => (
              <p className="vm-warning" key={item}>
                <AlertTriangle size={16} /> Missing: {item}
              </p>
            ))}
            {snapshot?.technical_conflicts.map((item) => (
              <p className="vm-warning" key={item}>
                <AlertTriangle size={16} /> {item}
              </p>
            ))}
          </div>
        </section>
      </div>

      <div className="vm-reasoning-grid vm-reasoning-grid--three">
        <EvidencePanel
          title="Triage and vitals"
          value={{
            triage: snapshot?.summaries.triage,
            vitals: snapshot?.summaries.vitals,
          }}
          empty="No triage or vital evidence in the current snapshot."
        />
        <EvidencePanel
          title="ECG summary"
          value={snapshot?.summaries.ecg}
          empty="No ECG evidence in the current snapshot."
        />
        <EvidencePanel
          title="Troponin summary"
          value={snapshot?.summaries.troponin}
          empty="No effective troponin evidence in the current snapshot."
        />
      </div>

      <section className="vm-card">
        <div className="vm-card__body">
          <h3>Select evidence for physician authorship</h3>
          <p>
            Selections are references to persisted records. They do not create a
            clinical conclusion.
          </p>
          <div className="vm-evidence-picker">
            {sourceOptions.map((source) => {
              const key = `${source.source_type}:${source.source_id}:v${source.source_version}`;
              return (
                <label key={key}>
                  <input
                    type="checkbox"
                    checked={supporting.includes(key)}
                    onChange={(event) =>
                      setSupporting(
                        toggle(supporting, key, event.target.checked),
                      )
                    }
                  />{" "}
                  Supporting - {source.source_type} v{source.source_version}
                </label>
              );
            })}
            {sourceOptions.map((source) => {
              const key = `${source.source_type}:${source.source_id}:v${source.source_version}`;
              return (
                <label key={`contra-${key}`}>
                  <input
                    type="checkbox"
                    checked={contradictory.includes(key)}
                    onChange={(event) =>
                      setContradictory(
                        toggle(contradictory, key, event.target.checked),
                      )
                    }
                  />{" "}
                  Contradictory - {source.source_type} v{source.source_version}
                </label>
              );
            })}
          </div>
        </div>
      </section>

      <div className="vm-reasoning-grid">
        <section className="vm-card">
          <div className="vm-card__body">
            <h3>
              <FilePenLine size={18} /> Physician assessment
            </h3>
            <form
              onSubmit={assessmentForm.handleSubmit((form) =>
                assessmentMutation.mutate(form),
              )}
              className="vm-form-stack"
            >
              <label>
                Assessment summary
                <textarea
                  {...assessmentForm.register("summary", { required: true })}
                />
              </label>
              <label>
                Uncertainty
                <textarea
                  {...assessmentForm.register("uncertainty", {
                    required: true,
                  })}
                />
              </label>
              <label>
                Additional information required
                <textarea
                  {...assessmentForm.register("additionalInformation")}
                />
              </label>
              {assessmentCorrection && (
                <label>
                  Correction reason
                  <textarea
                    {...assessmentForm.register("correctionReason", {
                      required: true,
                    })}
                  />
                </label>
              )}
              <button
                className="vm-button vm-button--primary"
                disabled={!snapshot || assessmentMutation.isPending}
              >
                {assessmentCorrection
                  ? "Append assessment correction"
                  : "Record physician assessment"}
              </button>
            </form>
            <MutationError error={assessmentMutation.error} />
          </div>
        </section>
        <History
          title="Assessment revision history"
          empty="No physician assessment recorded."
          items={value.assessments.map((item) => ({
            id: item.assessment_id,
            heading: `Revision ${item.revision_number}`,
            body: item.summary,
            meta: formatTimestamp(item.recorded_at),
            action: (
              <button
                className="vm-button"
                onClick={() => {
                  setAssessmentCorrection(item);
                  assessmentForm.reset({
                    summary: item.summary,
                    uncertainty: item.uncertainty,
                    additionalInformation:
                      item.additional_information_required ?? "",
                    correctionReason: "",
                  });
                }}
              >
                Create correction
              </button>
            ),
          }))}
        />
      </div>

      <div className="vm-reasoning-grid">
        <section className="vm-card">
          <div className="vm-card__body">
            <h3>Physician decision</h3>
            <form
              onSubmit={decisionForm.handleSubmit(setPendingDecision)}
              className="vm-form-stack"
            >
              <label>
                Documented plan
                <select
                  {...decisionForm.register("decisionType", { required: true })}
                >
                  {Object.entries(decisionLabels).map(([code, label]) => (
                    <option key={code} value={code}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Rationale
                <textarea
                  {...decisionForm.register("rationale", { required: true })}
                />
              </label>
              <label>
                Uncertainty
                <textarea
                  {...decisionForm.register("uncertainty", { required: true })}
                />
              </label>
              {decisionCorrection && (
                <label>
                  Correction reason
                  <textarea
                    {...decisionForm.register("correctionReason", {
                      required: true,
                    })}
                  />
                </label>
              )}
              <button
                className="vm-button vm-button--primary"
                disabled={!snapshot || !value.assessments.length}
              >
                Review and confirm
              </button>
            </form>
            <MutationError error={decisionMutation.error} />
          </div>
        </section>
        <History
          title="Decision correction and revocation history"
          empty="No physician decision recorded."
          items={value.decisions.map((item) => ({
            id: item.decision_id,
            heading: `${decisionLabel(item.decision_type)} - ${item.status}`,
            body: item.rationale,
            meta: `Revision ${item.revision_number} - ${item.effective ? "effective" : "not effective"}`,
            action: item.effective ? (
              <div className="vm-inline-actions">
                <button
                  className="vm-button"
                  onClick={() => {
                    setDecisionCorrection(item);
                    decisionForm.reset({
                      decisionType: item.decision_type as DecisionCode,
                      rationale: item.rationale,
                      uncertainty: item.uncertainty,
                      correctionReason: "",
                    });
                  }}
                >
                  Create correction
                </button>
                <button
                  className="vm-button vm-button--danger"
                  onClick={() => setRevokeDecision(item)}
                >
                  Revoke
                </button>
              </div>
            ) : undefined,
          }))}
        />
      </div>

      <nav
        className="vm-card vm-reasoning-links"
        aria-label="Related case workspaces"
      >
        <Link href={`/cases/${caseId}/ecg`}>ECG workspace</Link>
        <Link href={`/cases/${caseId}/troponin`}>Troponin workspace</Link>
        <Link href={`/cases/${caseId}/timeline`}>Timeline</Link>
        <Link href={`/cases/${caseId}/audit`}>Audit</Link>
      </nav>

      {pendingDecision && (
        <ConfirmationDialog
          title="Confirm physician decision"
          confirmLabel={
            pendingDecision.decisionType === "request_cath_lab_review"
              ? "Confirm physician request for cath-lab review"
              : "Record physician decision"
          }
          busy={decisionMutation.isPending}
          onCancel={() => setPendingDecision(null)}
          onConfirm={() => decisionMutation.mutate(pendingDecision)}
        >
          <p>
            This immutable record is linked to the current evidence snapshot and
            physician assessment.
          </p>
          <strong>{decisionLabels[pendingDecision.decisionType]}</strong>
          <p>
            No workflow transition or treatment action is performed by this
            dialog.
          </p>
        </ConfirmationDialog>
      )}
      {revokeDecision && (
        <ConfirmationDialog
          title="Revoke physician decision"
          confirmLabel="Append revocation"
          busy={revokeMutation.isPending}
          onCancel={() => setRevokeDecision(null)}
          onConfirm={() => revokeMutation.mutate()}
        >
          <label>
            Revocation reason
            <textarea
              value={revocationReason}
              onChange={(event) => setRevocationReason(event.target.value)}
            />
          </label>
          <p>
            The prior record remains auditable and will no longer authorize a
            future workflow transition.
          </p>
        </ConfirmationDialog>
      )}
    </main>
  );
}

function EvidencePanel({
  title,
  value,
  empty,
}: {
  title: string;
  value: unknown;
  empty: string;
}) {
  return (
    <section className="vm-card">
      <div className="vm-card__body">
        <h3>{title}</h3>
        {value ? (
          <pre className="vm-clinical-summary">
            {JSON.stringify(value, null, 2)}
          </pre>
        ) : (
          <p>{empty}</p>
        )}
      </div>
    </section>
  );
}

function History({
  title,
  empty,
  items,
}: {
  title: string;
  empty: string;
  items: Array<{
    id: string;
    heading: string;
    body: string;
    meta: string;
    action?: React.ReactNode;
  }>;
}) {
  return (
    <section className="vm-card">
      <div className="vm-card__body">
        <h3>{title}</h3>
        {!items.length && <p>{empty}</p>}
        {items.map((item) => (
          <article className="vm-history-row" key={item.id}>
            <div>
              <strong>{item.heading}</strong>
              <p>{item.body}</p>
              <small>{item.meta}</small>
            </div>
            {item.action}
          </article>
        ))}
      </div>
    </section>
  );
}

function ConfirmationDialog({
  title,
  confirmLabel,
  busy,
  onCancel,
  onConfirm,
  children,
}: {
  title: string;
  confirmLabel: string;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="vm-dialog-backdrop" role="presentation">
      <div
        className="vm-confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirmation-title"
      >
        <h3 id="confirmation-title">{title}</h3>
        {children}
        <div className="vm-inline-actions">
          <button className="vm-button" onClick={onCancel}>
            Cancel
          </button>
          <button
            className="vm-button vm-button--primary"
            disabled={busy}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function MutationError({ error }: { error: Error | null }) {
  return error ? (
    <p className="vm-warning" role="alert">
      <AlertTriangle size={16} /> {error.message}
    </p>
  ) : null;
}

function toggle(values: string[], value: string, checked: boolean) {
  return checked
    ? [...new Set([...values, value])]
    : values.filter((item) => item !== value);
}

function decisionLabel(code: string) {
  return code in decisionLabels ? decisionLabels[code as DecisionCode] : code;
}
