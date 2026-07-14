"use client";

import type {
  CorrectTriageInput,
  CorrectVitalsInput,
  RecordTriageInput,
  RecordVitalsInput,
} from "@vinami/api-client";
import {
  Badge,
  Button,
  ClinicalCard,
  EmptyState,
  TechnicalDetailsDisclosure,
} from "@vinami/ui";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import type {
  ClinicalDocumentationView,
  ObservationState,
  TriageAssessmentView,
  VitalObservationSetView,
} from "@web/entities/clinical-documentation/model";
import { createBrowserApiClient } from "@web/shared/api/browser";
import { formatTimestamp, shortReference } from "@web/shared/formatting";
import { TriageForm, type TriageFormValue } from "./triage-form";
import { VitalForm, type VitalFormValue } from "./vital-form";

type Editor =
  "triage-new" | "triage-correction" | "vitals-new" | "vitals-correction";

export function ClinicalDocumentationWorkspace({
  caseId,
  value,
}: {
  caseId: string;
  value: ClinicalDocumentationView;
}) {
  const router = useRouter();
  const api = useRef(createBrowserApiClient());
  const idempotencyKey = useRef(crypto.randomUUID());
  const [editor, setEditor] = useState<Editor | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submitTriage(form: TriageFormValue) {
    setBusy(true);
    setError(null);
    try {
      const content = triagePayload(form);
      if (editor === "triage-correction" && value.currentTriage) {
        const body: CorrectTriageInput = {
          ...content,
          expected_record_version: value.currentTriage.recordVersion,
          correction_reason: form.correctionReason,
        };
        await api.current.correctTriage(
          caseId,
          value.currentTriage.assessmentId,
          body,
          idempotencyKey.current,
        );
        setMessage("Triage correction recorded as a new revision.");
      } else {
        const body: RecordTriageInput = {
          ...content,
          expected_case_version: value.caseVersion,
        };
        await api.current.recordTriage(caseId, body, idempotencyKey.current);
        setMessage("Triage assessment recorded.");
      }
      finishMutation();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The request could not be completed.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function submitVitals(form: VitalFormValue) {
    const measurements = vitalMeasurements(form);
    if (measurements.length === 0) {
      setError("Enter at least one vital observation before review.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const observedAt = new Date(form.observedAt).toISOString();
      const content = {
        observed_at: observedAt,
        source: "vinami-next-clinical-workspace",
        measurements,
        supplemental_oxygen_state: "not_assessed" as const,
      };
      if (editor === "vitals-correction" && value.latestVitals) {
        const body: CorrectVitalsInput = {
          ...content,
          expected_record_version: value.latestVitals.recordVersion,
          correction_reason: form.correctionReason,
        };
        await api.current.correctVitals(
          caseId,
          value.latestVitals.vitalSetId,
          body,
          idempotencyKey.current,
        );
        setMessage("Vital correction recorded as a new revision.");
      } else {
        const body: RecordVitalsInput = {
          ...content,
          expected_case_version: value.caseVersion,
        };
        await api.current.recordVitals(caseId, body, idempotencyKey.current);
        setMessage("Vital observation set recorded.");
      }
      finishMutation();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The request could not be completed.",
      );
    } finally {
      setBusy(false);
    }
  }

  function finishMutation() {
    idempotencyKey.current = crypto.randomUUID();
    setEditor(null);
    router.refresh();
  }

  function open(next: Editor) {
    idempotencyKey.current = crypto.randomUUID();
    setError(null);
    setMessage(null);
    setEditor(next);
  }

  return (
    <section
      className="vm-documentation"
      aria-labelledby="documentation-heading"
    >
      <header className="vm-documentation__header">
        <div>
          <p className="vm-eyebrow">R2 verified vertical slice</p>
          <h2 id="documentation-heading">Triage and vital documentation</h2>
          <p>
            Structured observations only. No diagnosis, pathway, or clinical
            threshold is inferred.
          </p>
        </div>
        <Badge tone={value.missingDocumentation.length ? "warning" : "success"}>
          {value.missingDocumentation.length
            ? `${value.missingDocumentation.length} documentation gap${value.missingDocumentation.length > 1 ? "s" : ""}`
            : "Documentation policy complete"}
        </Badge>
      </header>

      {value.missingDocumentation.length > 0 && (
        <div className="vm-documentation-gaps" role="status">
          <strong>Documentation completeness review</strong>
          <ul>
            {value.missingDocumentation.map((item) => (
              <li key={item.identifier}>{item.description}</li>
            ))}
          </ul>
          <small>
            Backend policy {value.completenessPolicyVersion}; no clinical
            meaning is assigned.
          </small>
        </div>
      )}
      {message && (
        <div className="vm-banner vm-banner--success" role="status">
          {message}
        </div>
      )}
      {error && (
        <div className="vm-banner vm-banner--critical" role="alert">
          {error}
        </div>
      )}

      <div className="vm-documentation-grid">
        <ClinicalCard
          title="Structured triage"
          action={
            editor?.startsWith("triage") ? null : value.currentTriage ? (
              <Button type="button" onClick={() => open("triage-correction")}>
                Correct entry
              </Button>
            ) : (
              <Button
                type="button"
                className="vm-button--primary"
                onClick={() => open("triage-new")}
              >
                Record triage
              </Button>
            )
          }
        >
          {editor?.startsWith("triage") ? (
            <TriageForm
              current={
                editor === "triage-correction" ? value.currentTriage : null
              }
              busy={busy}
              onCancel={() => setEditor(null)}
              onSubmit={submitTriage}
            />
          ) : value.currentTriage ? (
            <TriageCurrent value={value.currentTriage} />
          ) : (
            <EmptyState
              title="No triage assessment recorded"
              description="Record explicit present, absent, unknown, or not-assessed states."
            />
          )}
        </ClinicalCard>

        <ClinicalCard
          title="Vital observations"
          action={
            editor?.startsWith("vitals") ? null : (
              <div className="vm-card-actions">
                {value.latestVitals && (
                  <Button
                    type="button"
                    onClick={() => open("vitals-correction")}
                  >
                    Correct latest
                  </Button>
                )}
                <Button
                  type="button"
                  className="vm-button--primary"
                  onClick={() => open("vitals-new")}
                >
                  Record new set
                </Button>
              </div>
            )
          }
        >
          {editor?.startsWith("vitals") ? (
            <VitalForm
              current={
                editor === "vitals-correction" ? value.latestVitals : null
              }
              busy={busy}
              onCancel={() => setEditor(null)}
              onSubmit={submitVitals}
            />
          ) : value.latestVitals ? (
            <VitalCurrent value={value.latestVitals} />
          ) : (
            <EmptyState
              title="No vital observation set"
              description="Record timestamped raw values with explicit units and source."
            />
          )}
        </ClinicalCard>
      </div>

      <ClinicalCard title="Documentation revision history">
        <div className="vm-revision-grid">
          <RevisionList
            title="Triage revisions"
            values={value.triageHistory}
            type="triage"
          />
          <RevisionList
            title="Vital-set revisions"
            values={value.vitalHistory}
            type="vitals"
          />
        </div>
        <TechnicalDetailsDisclosure title="Data provenance">
          <p>
            Data refreshed {formatTimestamp(value.dataFreshnessAt)}. Case
            aggregate version {value.caseVersion}. Corrections are append-only
            and visible in Timeline and Audit after outbox projection.
          </p>
        </TechnicalDetailsDisclosure>
      </ClinicalCard>
    </section>
  );
}

function TriageCurrent({ value }: { value: TriageAssessmentView }) {
  return (
    <div className="vm-current-record">
      <div className="vm-record-meta">
        <Badge tone={value.status === "correction" ? "warning" : "info"}>
          Revision {value.revisionNumber} · {value.status}
        </Badge>
        <span>
          Recorded {formatTimestamp(value.recordedAt)} by {value.recordedBy}
        </span>
      </div>
      <dl className="vm-definition-list">
        <dt>Chief complaint</dt>
        <dd>{value.chiefComplaint ?? "Not documented"}</dd>
        <dt>Onset</dt>
        <dd>
          {stateLabel(value.symptomOnsetState)}
          {value.symptomOnsetAt
            ? ` · ${formatTimestamp(value.symptomOnsetAt)}`
            : ""}
        </dd>
        <dt>Description</dt>
        <dd>{value.symptomDescription ?? "Not documented"}</dd>
      </dl>
      <ObservationRows
        title="Associated symptoms"
        values={value.associatedSymptoms}
      />
      <ObservationRows
        title="History / risk factors"
        values={value.riskFactors}
      />
      {value.correctionReason && (
        <p className="vm-correction-note">
          <strong>Correction reason:</strong> {value.correctionReason}
        </p>
      )}
    </div>
  );
}

function VitalCurrent({ value }: { value: VitalObservationSetView }) {
  return (
    <div className="vm-current-record">
      <div className="vm-record-meta">
        <Badge tone={value.correctionReason ? "warning" : "info"}>
          Set {value.sequenceNumber} · revision {value.revisionNumber}
        </Badge>
        <span>Observed {formatTimestamp(value.observedAt)}</span>
      </div>
      <div className="vm-vital-values">
        {value.measurements.map((item) => (
          <div key={item.kind}>
            <span>{labelKind(item.kind)}</span>
            <strong>
              {item.value} <small>{item.unit}</small>
            </strong>
            <small>{item.qualityStatus}</small>
          </div>
        ))}
      </div>
      {value.correctionReason && (
        <p className="vm-correction-note">
          <strong>Correction reason:</strong> {value.correctionReason}
        </p>
      )}
    </div>
  );
}

function ObservationRows({
  title,
  values,
}: {
  title: string;
  values: TriageAssessmentView["associatedSymptoms"];
}) {
  if (!values.length) return null;
  return (
    <div className="vm-observation-list">
      <strong>{title}</strong>
      {values.map((item) => (
        <span key={item.name}>
          {item.name}
          <Badge tone={item.state === "present" ? "info" : "neutral"}>
            {stateLabel(item.state)}
          </Badge>
        </span>
      ))}
    </div>
  );
}

function RevisionList({
  title,
  values,
  type,
}: {
  title: string;
  values: Array<TriageAssessmentView | VitalObservationSetView>;
  type: "triage" | "vitals";
}) {
  return (
    <div>
      <h3>{title}</h3>
      {values.length ? (
        <ol className="vm-revision-list">
          {values.map((item) => (
            <li
              key={
                type === "triage"
                  ? (item as TriageAssessmentView).assessmentId
                  : (item as VitalObservationSetView).vitalSetId
              }
            >
              <strong>Revision {item.revisionNumber}</strong>
              <span>
                {formatTimestamp(item.recordedAt)} · {item.recordedBy}
              </span>
              <small>
                {type === "triage"
                  ? shortReference(
                      (item as TriageAssessmentView).assessmentId,
                      "TRI",
                    )
                  : `Set ${(item as VitalObservationSetView).sequenceNumber}`}
              </small>
            </li>
          ))}
        </ol>
      ) : (
        <p>No revisions recorded.</p>
      )}
    </div>
  );
}

function triagePayload(
  form: TriageFormValue,
): Omit<RecordTriageInput, "expected_case_version"> {
  return {
    occurred_at: new Date().toISOString(),
    source: "vinami-next-clinical-workspace",
    chief_complaint: form.chiefComplaint || null,
    symptom_description: form.symptomDescription || null,
    symptom_onset_state: form.onsetState,
    symptom_onset_at:
      form.onsetState === "present"
        ? new Date(form.onsetAt).toISOString()
        : null,
    symptom_onset_precision:
      form.onsetState === "present" ? form.onsetPrecision : null,
    associated_symptoms: [
      { name: "dyspnoea", state: form.dyspnoea, note: null },
      { name: "nausea", state: form.nausea, note: null },
    ],
    cardiovascular_risk_factors: [
      { name: "smoking history", state: form.smokingHistory, note: null },
      { name: "diabetes history", state: form.diabetesHistory, note: null },
    ],
  };
}

function vitalMeasurements(
  form: VitalFormValue,
): RecordVitalsInput["measurements"] {
  const observedAt = new Date(form.observedAt).toISOString();
  const definitions = [
    ["heart_rate", form.heartRate, "beats/min"],
    ["systolic_blood_pressure", form.systolicBloodPressure, "mmHg"],
    ["diastolic_blood_pressure", form.diastolicBloodPressure, "mmHg"],
    ["respiratory_rate", form.respiratoryRate, "breaths/min"],
    ["oxygen_saturation", form.oxygenSaturation, "%"],
    ["body_temperature", form.bodyTemperature, "degC"],
    ["pain_score", form.painScore, "score"],
  ] as const;
  return definitions
    .filter(([, raw]) => raw.trim() !== "")
    .map(([kind, raw, unit]) => ({
      kind,
      value: Number(raw),
      unit,
      source: "vinami-next-clinical-workspace",
      observed_at: observedAt,
      quality_status: "unknown",
    }));
}

function stateLabel(value: ObservationState) {
  return value.replaceAll("_", " ");
}
function labelKind(value: string) {
  return value.replaceAll("_", " ");
}
