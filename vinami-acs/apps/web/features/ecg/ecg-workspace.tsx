"use client";

import { useState, useTransition } from "react";
import {
  Activity,
  BrainCircuit,
  CheckCircle2,
  FileHeart,
  ShieldAlert,
  Upload,
} from "lucide-react";
import { Badge, ClinicalCard } from "@vinami/ui";
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
  caseVersion,
  initialValue,
}: {
  caseId: string;
  caseVersion: number;
  initialValue: ECGWorkspaceView;
}) {
  const [value, setValue] = useState(initialValue);
  const [reviewSummary, setReviewSummary] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const api = createBrowserApiClient();
  const latestAnalysis = value.analyses[0] ?? null;

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
      form.set("expected_case_version", String(caseVersion));
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
    if (!value.currentStudy || !latestAnalysis || !reviewSummary.trim()) return;
    if (!window.confirm("Record this physician ECG review in the audit trail?"))
      return;
    execute(async () => {
      const currentVersion = value.interpretations[0]?.recordVersion ?? 0;
      await api.recordECGInterpretation(
        value.currentStudy!.studyId,
        {
          analysis_id: latestAnalysis.analysisId,
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

          <ClinicalCard title="AI-supported multi-label findings">
            {latestAnalysis ? (
              <AnalysisPanel
                value={latestAnalysis}
                suppress={value.quality?.suppressScoreEmphasis ?? false}
              />
            ) : (
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
            )}
          </ClinicalCard>

          {latestAnalysis ? (
            <ClinicalCard title="Physician ECG review">
              <div className="vm-review-layout">
                <div>
                  <label
                    className="vm-field-label"
                    htmlFor="ecg-review-summary"
                  >
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
                    <CheckCircle2 size={16} aria-hidden="true" /> Record
                    physician review
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
          ) : null}
        </div>
      )}
    </section>
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
              aria-valuetext={`${(finding.score * 100).toFixed(1)} percent; ${finding.positive ? "above" : "below"} the model threshold`}
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
