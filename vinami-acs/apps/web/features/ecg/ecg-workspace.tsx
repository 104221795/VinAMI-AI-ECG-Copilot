"use client";

import { useState, useTransition } from "react";
import {
  Activity,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  FileInput,
  FileHeart,
  RefreshCw,
  ShieldAlert,
  Upload,
} from "lucide-react";
import { Badge, ClinicalCard } from "@vinami/ui";
import type { ECGWaveform } from "@vinami/api-client";
import type { ECGWorkspaceView } from "@web/entities/ecg/model";
import { createBrowserApiClient } from "@web/shared/api/browser";
import { presentError } from "@web/shared/errors/presentation";
import { formatTimestamp, shortReference } from "@web/shared/formatting";
import { loadECGWorkspaceWith } from "./data";
import { WaveformGrid } from "./waveform-grid";

const LEADS = [
  "I",
  "II",
  "III",
  "aVR",
  "aVL",
  "aVF",
  "V1",
  "V2",
  "V3",
  "V4",
  "V5",
  "V6",
];

export function ECGWorkspace({
  caseId,
  initialValue,
}: {
  caseId: string;
  initialValue: ECGWorkspaceView;
}) {
  const [value, setValue] = useState(initialValue);
  const [reviewSummary, setReviewSummary] = useState("");
  const [comparisonReview, setComparisonReview] = useState("");
  const [baselineStudyId, setBaselineStudyId] = useState(
    initialValue.studies.at(-2)?.studyId ?? "",
  );
  const [currentStudyId, setCurrentStudyId] = useState(
    initialValue.currentStudy?.studyId ?? "",
  );
  const [baselineWaveform, setBaselineWaveform] =
    useState<ECGWorkspaceView["waveform"]>(null);
  const [currentWaveform, setCurrentWaveform] = useState<
    ECGWorkspaceView["waveform"]
  >(initialValue.waveform);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [reminderReason, setReminderReason] = useState(
    "Physician-requested repeat technical ECG review",
  );
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const api = createBrowserApiClient();
  const latestAnalysis =
    value.analyses.find(
      (analysis) => analysis.studyId === value.currentStudy?.studyId,
    ) ?? null;
  const latestInterpretation =
    value.interpretations.find(
      (item) => item.studyId === value.currentStudy?.studyId,
    ) ?? null;

  async function refresh() {
    setValue(await loadECGWorkspaceWith(api, caseId));
  }

  function execute(action: () => Promise<void>) {
    setError(null);
    setMessage(null);
    startTransition(() => {
      void action().catch((failure: unknown) => {
        setError(presentError(failure).description);
      });
    });
  }

  function addDemoStudy() {
    execute(async () => {
      const reference = `DEMO-12L-${new Date().toISOString().replaceAll(/\D/g, "").slice(0, 14)}`;
      const contentType = "application/vnd.vinami.ecg+json";
      const form = new FormData();
      form.set("source_type", "canonical_waveform");
      form.set("study_reference", reference);
      form.set("acquisition_at", new Date().toISOString());
      form.set("content_type", contentType);
      form.set(
        "artifact",
        new File(
          [JSON.stringify(demoWaveform(reference))],
          `${reference}.json`,
          {
            type: contentType,
          },
        ),
      );
      await api.uploadECGStudy(caseId, form, crypto.randomUUID());
      await refresh();
      setMessage("Synthetic 12-lead ECG ingested and quality assessed.");
    });
  }

  function uploadHospitalFile() {
    if (!uploadFile) return;
    execute(async () => {
      const sourceType =
        uploadFile.type === "application/pdf"
          ? "pdf_document"
          : uploadFile.name.toLowerCase().endsWith(".xml")
            ? "vendor_xml"
            : "dicom_file";
      const contentType =
        uploadFile.type ||
        (sourceType === "dicom_file" ? "application/dicom" : "application/xml");
      const reference = `LOCAL-${Date.now()}`;
      const form = new FormData();
      form.set("source_type", sourceType);
      form.set("study_reference", reference);
      form.set("acquisition_at", new Date().toISOString());
      form.set("content_type", contentType);
      form.set("artifact", uploadFile);
      await api.uploadECGStudy(caseId, form, crypto.randomUUID());
      setUploadFile(null);
      await refresh();
      setMessage(`${sourceType.replaceAll("_", " ")} stored with provenance.`);
    });
  }

  function importMockDICOM(reference: "R3-DICOM-001" | "R3-DICOM-RETRY") {
    execute(async () => {
      try {
        await api.importECGStudy(
          caseId,
          {
            source_type: "dicom_connector",
            source_connector_id: "mock-dicom-source",
            external_reference: reference,
            study_reference: `${reference}-${Date.now()}`,
            acquisition_at: new Date().toISOString(),
          },
          crypto.randomUUID(),
        );
      } catch (failure) {
        await refresh();
        throw failure;
      }
      await refresh();
      setMessage("Mock hospital DICOM request persisted.");
    });
  }

  function retryIngestion(jobId: string, recordVersion: number) {
    execute(async () => {
      await api.retryECGIngestion(
        jobId,
        { expected_version: recordVersion },
        crypto.randomUUID(),
      );
      await refresh();
      setMessage("Ingestion retry completed without creating a duplicate job.");
    });
  }

  function createComparison() {
    if (!baselineStudyId || !currentStudyId) return;
    execute(async () => {
      await api.createECGComparison(
        caseId,
        {
          baseline_study_id: baselineStudyId,
          current_study_id: currentStudyId,
        },
        crypto.randomUUID(),
      );
      const [baseline, current] = await Promise.all([
        api.getECGWaveform(baselineStudyId).catch(() => null),
        api.getECGWaveform(currentStudyId).catch(() => null),
      ]);
      setBaselineWaveform(baseline ? mapWaveform(baseline) : null);
      setCurrentWaveform(current ? mapWaveform(current) : null);
      await refresh();
      setMessage(
        "Technical serial ECG comparison persisted for physician review.",
      );
    });
  }

  function recordComparisonReview(comparisonId: string, version: number) {
    if (!comparisonReview.trim()) return;
    if (!window.confirm("Record this physician Dynamic ECG review?")) return;
    execute(async () => {
      await api.recordECGComparisonReview(
        comparisonId,
        {
          review_status: "reviewed",
          interpretation: comparisonReview.trim(),
          occurred_at: new Date().toISOString(),
          expected_version: version,
        },
        crypto.randomUUID(),
      );
      setComparisonReview("");
      await refresh();
      setMessage("Physician Dynamic ECG review recorded immutably.");
    });
  }

  function createReminder() {
    if (!value.currentStudy || !reminderReason.trim()) return;
    execute(async () => {
      await api.createECGReminder(
        caseId,
        {
          source_study_id: value.currentStudy!.studyId,
          reason: reminderReason.trim(),
          due_at: new Date(Date.now() + 30 * 60_000).toISOString(),
          origin: "physician_request",
        },
        crypto.randomUUID(),
      );
      await refresh();
      setMessage("Repeat ECG reminder scheduled by physician request.");
    });
  }

  function transitionReminder(
    reminder: ECGWorkspaceView["reminders"][number],
    action: "acknowledge" | "complete" | "cancel",
  ) {
    if (!window.confirm(`Confirm repeat ECG reminder action: ${action}?`))
      return;
    execute(async () => {
      const subsequent = value.studies.find(
        (study) => study.studyId !== reminder.sourceStudyId,
      );
      await api.transitionECGReminder(
        reminder.reminderId,
        action,
        {
          expected_version: reminder.recordVersion,
          completed_study_id:
            action === "complete" ? subsequent?.studyId : null,
          cancellation_reason:
            action === "cancel"
              ? "Physician cancelled demonstration reminder"
              : null,
        },
        crypto.randomUUID(),
      );
      await refresh();
      setMessage(`Repeat ECG reminder ${action} action recorded.`);
    });
  }

  function requestAnalysis() {
    if (!value.currentStudy) return;
    execute(async () => {
      await api.requestECGAnalysis(
        value.currentStudy!.studyId,
        { provider_name: "mock" },
        crypto.randomUUID(),
      );
      await refresh();
      setMessage("Deterministic research-use analysis completed.");
    });
  }

  function recordReview() {
    if (!value.currentStudy || !reviewSummary.trim()) return;
    if (!window.confirm("Record this physician ECG review in the audit trail?"))
      return;
    execute(async () => {
      const currentVersion =
        value.interpretations.find(
          (item) => item.studyId === value.currentStudy?.studyId,
        )?.recordVersion ?? 0;
      await api.recordECGInterpretation(
        value.currentStudy!.studyId,
        {
          analysis_id: latestAnalysis?.analysisId ?? null,
          interpretation_status: "reviewed",
          structured_interpretation: reviewSummary.trim(),
          agreement_status: "requires_clinical_correlation",
          quality_disposition: value.quality?.status ?? "not_assessed",
          repeat_ecg_requested: false,
          occurred_at: new Date().toISOString(),
          expected_version: currentVersion,
        },
        crypto.randomUUID(),
      );
      setReviewSummary("");
      await refresh();
      setMessage("Physician review recorded with model provenance.");
    });
  }

  return (
    <section className="vm-ecg-workspace" aria-labelledby="ecg-workspace-title">
      <div className="vm-section-heading">
        <div>
          <span className="vm-eyebrow">R3 ECG Intelligence</span>
          <h2 id="ecg-workspace-title">ECG review workspace</h2>
        </div>
        <Badge tone="warning">Research-use prototype</Badge>
      </div>
      <div className="vm-safety-banner" role="note">
        <ShieldAlert size={18} aria-hidden="true" />
        <span>
          ECG and model scores cannot rule out AMI or activate a cath lab.
          Physician review and clinical correlation are required.
        </span>
      </div>
      {message ? (
        <p className="vm-action-message vm-action-message--success">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="vm-action-message vm-action-message--error">{error}</p>
      ) : null}

      {!value.currentStudy ? (
        <div className="vm-section-stack">
          <div className="vm-ecg-empty">
            <FileHeart size={28} aria-hidden="true" />
            <div>
              <h3>No ECG study recorded for this case</h3>
              <p>
                Load a deterministic synthetic waveform to exercise the R3
                clinical workflow.
              </p>
            </div>
            <button
              className="vm-button vm-button--primary"
              disabled={isPending}
              onClick={addDemoStudy}
            >
              <Upload size={16} aria-hidden="true" />
              {isPending ? "Processing..." : "Load synthetic 12-lead ECG"}
            </button>
          </div>
          {supportsHospitalIngestion(value) ? (
            <SourceIntegrationPanel
              value={value}
              uploadFile={uploadFile}
              isPending={isPending}
              onFile={setUploadFile}
              onUpload={uploadHospitalFile}
              onImport={importMockDICOM}
              onRetry={retryIngestion}
            />
          ) : null}
        </div>
      ) : (
        <div className="vm-section-stack">
          <section
            className="vm-ecg-status-strip"
            aria-label="Current ECG status"
          >
            <StatusMetric
              label="Study"
              value={value.currentStudy.studyReference}
            />
            <StatusMetric
              label="Quality"
              value={value.quality?.status ?? "pending"}
            />
            <StatusMetric
              label="Acquired"
              value={formatTimestamp(value.currentStudy.acquisitionAt)}
            />
            <StatusMetric
              label="Analysis"
              value={latestAnalysis?.status ?? "not requested"}
            />
          </section>

          <ClinicalCard title="Twelve-lead waveform">
            <div className="vm-panel-toolbar">
              <p>
                {value.currentStudy.samplingRateHz ?? "-"} Hz ·{" "}
                {value.currentStudy.durationSeconds ?? "-"} s ·{" "}
                {value.currentStudy.amplitudeUnit ?? "unit unavailable"}
              </p>
              <button
                className="vm-button vm-button--secondary"
                disabled={isPending}
                onClick={addDemoStudy}
              >
                <Upload size={15} aria-hidden="true" /> Add serial ECG
              </button>
            </div>
            {value.waveform ? (
              <WaveformGrid value={value.waveform} />
            ) : (
              <p className="vm-inline-empty">
                Structured waveform is unavailable for this study.
              </p>
            )}
          </ClinicalCard>

          <div className="vm-layout-split vm-layout-split--ecg">
            <ClinicalCard title="Technical quality">
              <QualityPanel value={value} />
            </ClinicalCard>
            <ClinicalCard title="Serial evidence">
              <SerialPanel value={value} />
            </ClinicalCard>
          </div>

          <AIPathPanel
            value={value}
            latestAnalysis={latestAnalysis}
            latestInterpretation={latestInterpretation}
          />

          <ClinicalCard title="AI-supported multi-label findings">
            {latestAnalysis ? (
              <AnalysisPanel
                value={latestAnalysis}
                suppress={value.quality?.suppressScoreEmphasis ?? false}
              />
            ) : value.currentStudy.waveformAvailable ? (
              <div className="vm-inline-action">
                <BrainCircuit size={22} aria-hidden="true" />
                <div>
                  <strong>No model analysis for the current study</strong>
                  <p>
                    Run the deterministic mock provider to verify the normalized
                    contract.
                  </p>
                </div>
                <button
                  className="vm-button vm-button--primary"
                  disabled={isPending}
                  onClick={requestAnalysis}
                >
                  Run research-use analysis
                </button>
              </div>
            ) : (
              <p className="vm-inline-empty">
                Automated waveform analysis is unavailable for a document-only
                ECG study.
              </p>
            )}
          </ClinicalCard>

          <ClinicalCard
            title={
              value.currentStudy.waveformAvailable
                ? "Physician ECG review"
                : "Physician document review"
            }
          >
            <div className="vm-review-layout">
              <div>
                <label className="vm-field-label" htmlFor="ecg-review-summary">
                  Structured review summary
                </label>
                <textarea
                  id="ecg-review-summary"
                  value={reviewSummary}
                  onChange={(event) => setReviewSummary(event.target.value)}
                  placeholder="Document physician interpretation and clinical correlation"
                  rows={4}
                />
                <button
                  className="vm-button vm-button--primary"
                  disabled={isPending || !reviewSummary.trim()}
                  onClick={recordReview}
                >
                  <CheckCircle2 size={16} aria-hidden="true" /> Record physician
                  review
                </button>
              </div>
              <div className="vm-review-history">
                <h3>Review history</h3>
                {value.interpretations.length ? (
                  value.interpretations.map((item) => (
                    <article key={item.interpretationId}>
                      <strong>{item.status.replaceAll("_", " ")}</strong>
                      <p>{item.summary}</p>
                      <small>
                        {item.actorRole} · {formatTimestamp(item.recordedAt)}
                      </small>
                    </article>
                  ))
                ) : (
                  <p>No physician interpretation recorded.</p>
                )}
              </div>
            </div>
          </ClinicalCard>

          {supportsHospitalIngestion(value) ? (
            <SourceIntegrationPanel
              value={value}
              uploadFile={uploadFile}
              isPending={isPending}
              onFile={setUploadFile}
              onUpload={uploadHospitalFile}
              onImport={importMockDICOM}
              onRetry={retryIngestion}
            />
          ) : null}

          {value.capabilities.dynamic_ecg ? (
            <DynamicECGPanel
              value={value}
              baselineStudyId={baselineStudyId}
              currentStudyId={currentStudyId}
              baselineWaveform={baselineWaveform}
              currentWaveform={currentWaveform}
              comparisonReview={comparisonReview}
              isPending={isPending}
              onBaseline={setBaselineStudyId}
              onCurrent={setCurrentStudyId}
              onCompare={createComparison}
              onReviewText={setComparisonReview}
              onReview={recordComparisonReview}
            />
          ) : null}

          {value.capabilities.repeat_ecg ? (
            <RepeatECGPanel
              value={value}
              reason={reminderReason}
              isPending={isPending}
              onReason={setReminderReason}
              onCreate={createReminder}
              onTransition={transitionReminder}
            />
          ) : null}
        </div>
      )}
    </section>
  );
}

function AIPathPanel({
  value,
  latestAnalysis,
  latestInterpretation,
}: {
  value: ECGWorkspaceView;
  latestAnalysis: ECGWorkspaceView["analyses"][number] | null;
  latestInterpretation: ECGWorkspaceView["interpretations"][number] | null;
}) {
  const study = value.currentStudy;
  const machineStatus = latestAnalysis
    ? latestAnalysis.status
    : study?.waveformAvailable
      ? "pending"
      : "technically limited";
  const providerLabel = latestAnalysis
    ? latestAnalysis.synthetic
      ? `Synthetic/mock provider: ${latestAnalysis.providerName}`
      : `Provider: ${latestAnalysis.providerName}`
    : "No provider result recorded";
  const steps = [
    {
      label: "ECG acquired",
      status: study ? "available" : "missing",
      detail: study
        ? `${study.studyReference} - ${formatTimestamp(study.acquisitionAt)}`
        : "No ECG study selected.",
      source: "ECG study",
      tone: "evidence",
    },
    {
      label: "Technical quality check",
      status: value.quality?.status ?? "pending",
      detail: value.quality
        ? `${value.quality.engineVersion} - ${value.quality.reasonCodes.join(", ") || "no reason code"}`
        : "Quality assessment has not been recorded.",
      source: "Machine-generated evidence",
      tone: "machine",
    },
    {
      label: "Model inference",
      status: machineStatus,
      detail: latestAnalysis
        ? `${latestAnalysis.modelName} ${latestAnalysis.modelVersion} - ${latestAnalysis.completedAt ? formatTimestamp(latestAnalysis.completedAt) : "completion time unavailable"}`
        : "Run research-use analysis only when waveform input is available.",
      source: providerLabel,
      tone: "machine",
    },
    {
      label: "Model result and explanation",
      status: latestAnalysis?.explanationStatus ?? "pending",
      detail: latestAnalysis
        ? `${latestAnalysis.findings.length} model score(s). Scores are not disease probabilities.`
        : "No model score or explanation reference recorded.",
      source: "AI-supported finding",
      tone: "machine",
    },
    {
      label: "Physician ECG review",
      status: latestInterpretation ? latestInterpretation.status : "pending",
      detail: latestInterpretation
        ? latestInterpretation.summary
        : "Physician interpretation is required before clinical authority.",
      source: "Physician-authored interpretation",
      tone: "physician",
    },
    {
      label: "Evidence snapshot and decision",
      status: latestInterpretation ? "under review" : "not started",
      detail:
        "Clinical Reasoning owns evidence synthesis, assessment and physician decision.",
      source: "Clinical Reasoning workspace",
      tone: "authority",
    },
  ];
  return (
    <ClinicalCard title="AI-supported ECG path">
      <div className="vm-ai-path" aria-label="AI-supported ECG evidence path">
        {steps.map((step) => (
          <article
            className={`vm-ai-step vm-ai-step--${step.tone}`}
            key={step.label}
          >
            <span
              className={`vm-status-pill vm-status-pill--${step.status.replaceAll(" ", "-")}`}
            >
              {step.status}
            </span>
            <h3>{step.label}</h3>
            <p>{step.detail}</p>
            <small>{step.source}</small>
          </article>
        ))}
      </div>
      <p className="vm-safety-note">
        Machine-generated ECG evidence is visually separated from
        physician-authored interpretation and physician-authorized decisions. AI
        output cannot create tasks, alerts, workflow transitions or cath-lab
        authority.
      </p>
    </ClinicalCard>
  );
}

function SourceIntegrationPanel({
  value,
  uploadFile,
  isPending,
  onFile,
  onUpload,
  onImport,
  onRetry,
}: {
  value: ECGWorkspaceView;
  uploadFile: File | null;
  isPending: boolean;
  onFile: (file: File | null) => void;
  onUpload: () => void;
  onImport: (reference: "R3-DICOM-001" | "R3-DICOM-RETRY") => void;
  onRetry: (jobId: string, version: number) => void;
}) {
  return (
    <ClinicalCard title="Source and integration">
      <div className="vm-source-actions">
        <div>
          <span className="vm-field-label">Local hospital-format artifact</span>
          <input
            aria-label="DICOM XML or PDF ECG file"
            type="file"
            accept=".dcm,.dicom,.xml,.pdf,application/dicom,application/xml,application/pdf"
            onChange={(event) => onFile(event.target.files?.[0] ?? null)}
          />
          <button
            className="vm-button vm-button--secondary"
            disabled={!uploadFile || isPending}
            onClick={onUpload}
          >
            <FileInput size={15} aria-hidden="true" /> Import selected file
          </button>
        </div>
        <div>
          <span className="vm-field-label">
            Deterministic hospital connector
          </span>
          <button
            className="vm-button vm-button--secondary"
            disabled={isPending}
            onClick={() => onImport("R3-DICOM-001")}
          >
            Import mock DICOM
          </button>
          <button
            className="vm-button vm-button--secondary"
            disabled={isPending}
            onClick={() => onImport("R3-DICOM-RETRY")}
          >
            Exercise timeout path
          </button>
        </div>
      </div>
      <div className="vm-connector-grid">
        {value.connectors.map((connector) => (
          <article key={connector.connectorId} className="vm-integration-item">
            <div>
              <strong>{connector.displayName}</strong>
              <Badge tone={connector.available ? "success" : "critical"}>
                {connector.available ? "Available" : "Unavailable"}
              </Badge>
            </div>
            <p>{connector.detail}</p>
            <small>
              {connector.connectorType.replaceAll("_", " ")} ·{" "}
              {connector.profile ?? "No profile"} ·{" "}
              {connector.version ?? "Unknown version"}
            </small>
          </article>
        ))}
      </div>
      <div className="vm-ingestion-list" aria-label="ECG ingestion jobs">
        {value.ingestionJobs.length ? (
          value.ingestionJobs.map((job) => (
            <article key={job.jobId} className="vm-integration-item">
              <div>
                <strong>{job.sourceType.replaceAll("_", " ")}</strong>
                <Badge
                  tone={
                    job.status === "completed"
                      ? "success"
                      : job.status === "failed"
                        ? "critical"
                        : "warning"
                  }
                >
                  {job.status.replaceAll("_", " ")}
                </Badge>
              </div>
              <p>
                {job.connectorId ?? "Local upload"} · requested{" "}
                {formatTimestamp(job.requestedAt)}
              </p>
              <small>
                Parser {job.parser ?? "pending"} {job.parserVersion ?? ""} ·
                retries {job.retryCount}
              </small>
              {job.failureDetail ? (
                <p className="vm-action-message vm-action-message--error">
                  {job.failureDetail}
                </p>
              ) : null}
              {job.status === "failed" ? (
                <button
                  className="vm-button vm-button--secondary"
                  disabled={isPending}
                  onClick={() => onRetry(job.jobId, job.recordVersion)}
                >
                  <RefreshCw size={14} aria-hidden="true" /> Safe retry
                </button>
              ) : null}
              <details>
                <summary>Technical details</summary>
                <code>{job.correlationId}</code>
                {job.warnings.map((warning) => (
                  <p key={warning}>{warning}</p>
                ))}
              </details>
            </article>
          ))
        ) : (
          <p className="vm-inline-empty">
            No ingestion job has been requested.
          </p>
        )}
      </div>
      {value.currentStudy?.sourceType === "pdf_document" ? (
        <div className="vm-pdf-state">
          <div className="vm-safety-banner" role="note">
            Source document only. Structured waveform and automated waveform
            analysis are unavailable.
          </div>
          <iframe
            title="PDF ECG source document preview"
            src={`/api/backend/api/v1/ecg-studies/${value.currentStudy.studyId}/preview`}
          />
        </div>
      ) : null}
    </ClinicalCard>
  );
}

function DynamicECGPanel({
  value,
  baselineStudyId,
  currentStudyId,
  baselineWaveform,
  currentWaveform,
  comparisonReview,
  isPending,
  onBaseline,
  onCurrent,
  onCompare,
  onReviewText,
  onReview,
}: {
  value: ECGWorkspaceView;
  baselineStudyId: string;
  currentStudyId: string;
  baselineWaveform: ECGWorkspaceView["waveform"];
  currentWaveform: ECGWorkspaceView["waveform"];
  comparisonReview: string;
  isPending: boolean;
  onBaseline: (value: string) => void;
  onCurrent: (value: string) => void;
  onCompare: () => void;
  onReviewText: (value: string) => void;
  onReview: (comparisonId: string, version: number) => void;
}) {
  const comparison = value.comparisons[0] ?? null;
  return (
    <ClinicalCard title="Dynamic ECG">
      <p className="vm-score-explainer">
        Technical ECG change indicator — physician interpretation required.
      </p>
      <div className="vm-comparison-controls">
        <label>
          Baseline study
          <select
            value={baselineStudyId}
            onChange={(event) => onBaseline(event.target.value)}
          >
            <option value="">Select baseline</option>
            {value.studies.map((study) => (
              <option key={study.studyId} value={study.studyId}>
                {study.studyReference} · {formatTimestamp(study.acquisitionAt)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Current study
          <select
            value={currentStudyId}
            onChange={(event) => onCurrent(event.target.value)}
          >
            <option value="">Select current</option>
            {value.studies.map((study) => (
              <option key={study.studyId} value={study.studyId}>
                {study.studyReference} · {formatTimestamp(study.acquisitionAt)}
              </option>
            ))}
          </select>
        </label>
        <button
          className="vm-button vm-button--primary"
          disabled={
            isPending ||
            !baselineStudyId ||
            !currentStudyId ||
            baselineStudyId === currentStudyId
          }
          onClick={onCompare}
        >
          Compare technical signals
        </button>
      </div>
      {comparison ? (
        <div className="vm-section-stack">
          <div className="vm-comparison-summary">
            <StatusMetric
              label="Comparability"
              value={comparison.comparabilityStatus}
            />
            <StatusMetric
              label="Score compatibility"
              value={comparison.scoreCompatibility}
            />
            <StatusMetric label="Policy" value={comparison.policyVersion} />
          </div>
          {comparison.comparabilityReasons.length ? (
            <div className="vm-safety-banner" role="status">
              {comparison.comparabilityReasons
                .map((reason) => reason.replaceAll("_", " "))
                .join(" · ")}
            </div>
          ) : null}
          <div
            className="vm-dynamic-waveforms"
            aria-label="Synchronized serial ECG waveforms"
          >
            <div>
              <h3>Baseline</h3>
              {baselineWaveform ? (
                <WaveformGrid value={baselineWaveform} />
              ) : (
                <p>Load comparison to view the structured waveform.</p>
              )}
            </div>
            <div>
              <h3>Current</h3>
              {currentWaveform ? (
                <WaveformGrid value={currentWaveform} />
              ) : (
                <p>Structured waveform unavailable.</p>
              )}
            </div>
          </div>
          {comparison.leadComparisons.length ? (
            <div className="vm-table-scroll">
              <table>
                <caption>Lead-by-lead non-diagnostic technical metrics</caption>
                <thead>
                  <tr>
                    <th>Lead</th>
                    <th>Similarity</th>
                    <th>Normalized difference</th>
                    <th>Baseline shift</th>
                    <th>Alignment</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.leadComparisons.map((lead) => (
                    <tr key={lead.leadName}>
                      <th>{lead.leadName}</th>
                      <td>{lead.waveformSimilarity.toFixed(3)}</td>
                      <td>{lead.normalizedDifference.toFixed(3)}</td>
                      <td>{lead.baselineShiftIndicator.toFixed(3)}</td>
                      <td>{lead.sampleAlignmentStatus.replaceAll("_", " ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {comparison.scoreEvolution.length ? (
            <div className="vm-score-evolution">
              <h3>Compatible model-score evolution</h3>
              {comparison.scoreEvolution.map((score) => (
                <div key={score.findingCode}>
                  <strong>{score.findingCode}</strong>
                  <span>
                    {score.previousScore.toFixed(3)} →{" "}
                    {score.currentScore.toFixed(3)}
                  </span>
                  <small>
                    Δ {score.absoluteDelta.toFixed(3)} ·{" "}
                    {score.compatibilityStatus}
                  </small>
                </div>
              ))}
            </div>
          ) : (
            <p>
              Score deltas are withheld when model or preprocessing provenance
              is incompatible.
            </p>
          )}
          <label className="vm-field-label" htmlFor="dynamic-review">
            Physician comparison review
          </label>
          <textarea
            id="dynamic-review"
            rows={3}
            value={comparisonReview}
            onChange={(event) => onReviewText(event.target.value)}
          />
          <button
            className="vm-button vm-button--primary"
            disabled={isPending || !comparisonReview.trim()}
            onClick={() =>
              onReview(
                comparison.comparisonId,
                value.comparisonReviews.find(
                  (review) => review.comparisonId === comparison.comparisonId,
                )?.recordVersion ?? 0,
              )
            }
          >
            Record physician review
          </button>
        </div>
      ) : (
        <p className="vm-inline-empty">
          Select two structured studies to assess technical comparability.
        </p>
      )}
    </ClinicalCard>
  );
}

function RepeatECGPanel({
  value,
  reason,
  isPending,
  onReason,
  onCreate,
  onTransition,
}: {
  value: ECGWorkspaceView;
  reason: string;
  isPending: boolean;
  onReason: (value: string) => void;
  onCreate: () => void;
  onTransition: (
    reminder: ECGWorkspaceView["reminders"][number],
    action: "acknowledge" | "complete" | "cancel",
  ) => void;
}) {
  return (
    <ClinicalCard title="Repeat ECG workflow">
      <div className="vm-inline-action">
        <Clock3 size={22} aria-hidden="true" />
        <div>
          <label className="vm-field-label" htmlFor="repeat-reason">
            Reason
          </label>
          <input
            id="repeat-reason"
            value={reason}
            onChange={(event) => onReason(event.target.value)}
          />
        </div>
        <button
          className="vm-button vm-button--primary"
          disabled={isPending || !value.currentStudy || !reason.trim()}
          onClick={onCreate}
        >
          Schedule +30 min
        </button>
      </div>
      <div className="vm-ingestion-list">
        {value.reminders.map((reminder) => (
          <article key={reminder.reminderId} className="vm-integration-item">
            <div>
              <strong>{reminder.reason}</strong>
              <Badge
                tone={
                  reminder.status === "completed"
                    ? "success"
                    : reminder.status === "overdue"
                      ? "critical"
                      : "warning"
                }
              >
                {reminder.status}
              </Badge>
            </div>
            <p>
              Due {formatTimestamp(reminder.dueAt)} ·{" "}
              {reminder.origin.replaceAll("_", " ")} · requested by{" "}
              {reminder.requestedByRole}
            </p>
            {reminder.completedAt ? (
              <small>Completed {formatTimestamp(reminder.completedAt)}</small>
            ) : null}
            {reminder.cancellationReason ? (
              <small>{reminder.cancellationReason}</small>
            ) : null}
            {!["completed", "cancelled"].includes(reminder.status) ? (
              <div className="vm-case-header">
                {reminder.status !== "acknowledged" ? (
                  <button
                    className="vm-button vm-button--secondary"
                    onClick={() => onTransition(reminder, "acknowledge")}
                  >
                    Acknowledge
                  </button>
                ) : null}
                <button
                  className="vm-button vm-button--secondary"
                  disabled={value.studies.length < 2}
                  onClick={() => onTransition(reminder, "complete")}
                >
                  Complete with subsequent ECG
                </button>
                <button
                  className="vm-button vm-button--secondary"
                  onClick={() => onTransition(reminder, "cancel")}
                >
                  Cancel
                </button>
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </ClinicalCard>
  );
}

function StatusMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value.replaceAll("_", " ")}</strong>
    </div>
  );
}

function QualityPanel({ value }: { value: ECGWorkspaceView }) {
  if (!value.quality) return <p>Quality assessment pending.</p>;
  return (
    <div className="vm-quality-panel">
      <div
        className={`vm-quality-mark vm-quality-mark--${value.quality.status}`}
      >
        <Activity size={18} aria-hidden="true" /> {value.quality.status}
      </div>
      <dl className="vm-definition-list">
        <dt>Engine</dt>
        <dd>{value.quality.engineVersion}</dd>
        <dt>Affected leads</dt>
        <dd>{value.quality.affectedLeads.join(", ") || "None detected"}</dd>
        <dt>Reason codes</dt>
        <dd>{value.quality.reasonCodes.join(", ") || "None"}</dd>
      </dl>
    </div>
  );
}

function SerialPanel({ value }: { value: ECGWorkspaceView }) {
  return (
    <div>
      <strong>
        {value.studies.length} ECG{" "}
        {value.studies.length === 1 ? "study" : "studies"}
      </strong>
      <ol className="vm-serial-list">
        {[...value.studies].reverse().map((study, index) => (
          <li key={study.studyId}>
            <span>{index === 0 ? "Current" : `Prior ${index}`}</span>
            <strong>{study.studyReference}</strong>
            <small>
              {formatTimestamp(study.acquisitionAt)} · {study.qualityStatus}
            </small>
          </li>
        ))}
      </ol>
      {value.comparisons.length ? (
        <p>{value.comparisons.length} technical comparison recorded.</p>
      ) : (
        <p>Comparison becomes available after a serial pair is requested.</p>
      )}
    </div>
  );
}

function AnalysisPanel({
  value,
  suppress,
}: {
  value: ECGWorkspaceView["analyses"][number];
  suppress: boolean;
}) {
  return (
    <div className="vm-analysis-panel">
      <div className="vm-model-provenance">
        <div>
          <span>Model</span>
          <strong>{value.modelName}</strong>
        </div>
        <div>
          <span>Version</span>
          <strong>{value.modelVersion}</strong>
        </div>
        <div>
          <span>Provider</span>
          <strong>{value.providerName}</strong>
        </div>
        <div>
          <span>Run</span>
          <strong>{shortReference(value.analysisId, "AI")}</strong>
        </div>
      </div>
      <p className="vm-score-explainer">
        Five independent model outputs, ranked high to low. A threshold crossing
        marks review priority; it is not a diagnosis and the scores do not need
        to sum to 1.
      </p>
      {suppress ? (
        <div className="vm-safety-banner vm-safety-banner--critical">
          Technical quality blocks normal score emphasis.
        </div>
      ) : null}
      <ol
        className={`vm-finding-list${suppress ? " vm-finding-list--suppressed" : ""}`}
      >
        {value.findings.map((finding) => (
          <li key={finding.code}>
            <span className="vm-finding-rank">{finding.rank}</span>
            <div className="vm-finding-label">
              <strong>{finding.code}</strong>
              <span>{finding.label}</span>
            </div>
            <div
              className="vm-score-track"
              role="progressbar"
              aria-label={`${finding.code} model score ${finding.score.toFixed(3)}`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(finding.score * 100)}
              aria-valuetext={`${(finding.score * 100).toFixed(1)} percent; ${finding.thresholdMet ? "above" : "below"} the model threshold`}
            >
              <span style={{ width: `${finding.score * 100}%` }} />
              {finding.threshold !== null ? (
                <i style={{ left: `${finding.threshold * 100}%` }} />
              ) : null}
            </div>
            <div className="vm-finding-value">
              <strong>{finding.score.toFixed(3)}</strong>
              <span>{finding.thresholdMet ? "Review" : "Below threshold"}</span>
            </div>
          </li>
        ))}
      </ol>
      <p className="vm-model-warning">
        {value.safetyNotice} {value.warnings.join(" ")}
      </p>
    </div>
  );
}

function demoWaveform(reference: string) {
  const sampleCount = 1000;
  return {
    schema_version: "1.0",
    study_reference: reference,
    sampling_rate_hz: 100,
    amplitude_unit: "uV",
    acquisition_at: new Date().toISOString(),
    lead_order: LEADS,
    leads: LEADS.map((name, leadIndex) => ({
      name,
      samples: Array.from({ length: sampleCount }, (_, index) => {
        const phase = (index % 100) / 100;
        const baseline = 38 * Math.sin(index / 23 + leadIndex * 0.19);
        const qrs =
          phase > 0.46 && phase < 0.5
            ? 780 * (1 - Math.abs(phase - 0.48) / 0.02)
            : 0;
        const tWave = 110 * Math.exp(-Math.pow((phase - 0.72) / 0.11, 2));
        return Math.round((baseline + qrs + tWave) * (1 - leadIndex * 0.018));
      }),
    })),
  };
}

function mapWaveform(
  value: ECGWaveform,
): NonNullable<ECGWorkspaceView["waveform"]> {
  return {
    studyReference: value.study_reference,
    samplingRateHz: value.sampling_rate_hz,
    amplitudeUnit: value.amplitude_unit,
    leads: value.leads,
  };
}

function supportsHospitalIngestion(value: ECGWorkspaceView): boolean {
  return [
    "local_dicom",
    "mock_dicom_connector",
    "canonical_xml",
    "pdf_document",
  ].some((capability) => value.capabilities[capability] === true);
}
