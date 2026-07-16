"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, RefreshCw, Save } from "lucide-react";
import { useMemo, useState } from "react";
import {
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  StatusBadge,
} from "@vinami/ui";
import { createBrowserApiClient } from "@web/shared/api/browser";
import { presentError } from "@web/shared/errors/presentation";
import { formatTimestamp, shortReference } from "@web/shared/formatting";
import {
  correctOutcomeWith,
  loadModelProvenanceWith,
  loadOutcomeHistoryWith,
  recordOutcomeWith,
  requestResearchExportWith,
} from "./data";
import type {
  ModelProvenanceView,
  OutcomeHistoryView,
  ResearchExportView,
} from "./model";

interface OutcomeFormState {
  outcome_type: string;
  outcome_timestamp: string;
  final_conclusion: string;
  disposition: string;
  destination: string;
  data_completeness: string;
  source: string;
  uncertainty: string;
  unavailable_reason: string;
  correction_reason: string;
}

export function CaseHistoryPanel({
  caseId,
  initialOutcomes,
  initialProvenance,
}: {
  caseId: string;
  initialOutcomes: OutcomeHistoryView;
  initialProvenance: ModelProvenanceView[];
}) {
  const api = useMemo(() => createBrowserApiClient(), []);
  const queryClient = useQueryClient();
  const outcomes = useQuery({
    queryKey: ["r9-outcomes", caseId],
    queryFn: () => loadOutcomeHistoryWith(api, caseId),
    initialData: initialOutcomes,
  });
  const provenance = useQuery({
    queryKey: ["r9-model-provenance", caseId],
    queryFn: () => loadModelProvenanceWith(api, caseId),
    initialData: initialProvenance,
  });
  const [form, setForm] = useState(() => ({
    outcome_type: "disposition",
    outcome_timestamp: new Date().toISOString(),
    final_conclusion: "",
    disposition: "",
    destination: "",
    data_completeness: "documented",
    source: "physician_documented",
    uncertainty: "",
    unavailable_reason: "",
    correction_reason: "",
  }));
  const [exportResult, setExportResult] = useState<ResearchExportView | null>(
    null,
  );
  const saveOutcome = useMutation({
    mutationFn: async () => {
      const current = outcomes.data.current;
      const payload = cleanPayload(form);
      return current
        ? correctOutcomeWith(
            api,
            caseId,
            current.outcomeId,
            payload,
            `r9-correct-outcome-${crypto.randomUUID()}`,
          )
        : recordOutcomeWith(
            api,
            caseId,
            payload,
            `r9-record-outcome-${crypto.randomUUID()}`,
          );
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["r9-outcomes", caseId],
      });
      setForm((value) => ({
        ...value,
        final_conclusion: "",
        correction_reason: "",
        uncertainty: "",
      }));
    },
  });
  const exportMutation = useMutation({
    mutationFn: () =>
      requestResearchExportWith(
        api,
        caseId,
        `r9-export-${crypto.randomUUID()}`,
      ),
    onSuccess: setExportResult,
  });

  if (outcomes.isLoading || provenance.isLoading) return <LoadingSkeleton />;
  if (outcomes.isError || provenance.isError) {
    const error = presentError(outcomes.error ?? provenance.error);
    return <ErrorState {...error} />;
  }

  const current = outcomes.data.current;
  return (
    <section className="vm-r9-grid" aria-label="Outcome and learning record">
      <div className="vm-card">
        <header className="vm-card__header">
          <div>
            <h2>Clinical Outcome</h2>
            <p>Physician-authored or explicitly sourced. Never inferred.</p>
          </div>
          <button
            className="vm-button vm-button--secondary"
            onClick={() => outcomes.refetch()}
            disabled={outcomes.isFetching}
          >
            <RefreshCw size={15} aria-hidden />
            Refresh
          </button>
        </header>
        <div className="vm-card__body vm-r9-outcome">
          {current ? (
            <div className="vm-r9-current">
              <StatusBadge status={`revision ${current.revisionNumber}`} />
              <h3>{current.finalConclusion}</h3>
              <p>
                {current.outcomeType} recorded{" "}
                {formatTimestamp(current.recordedAt)} by{" "}
                {shortReference(current.recordedBy, "ACT")}
              </p>
              <p>
                {current.disposition ?? "Disposition not documented"} -{" "}
                {current.destination ?? "Destination not documented"}
              </p>
            </div>
          ) : (
            <EmptyState
              title="No outcome recorded"
              description="Missing outcome data remains missing; task completion and workflow state do not create an outcome."
            />
          )}
          <OutcomeForm
            value={form}
            correcting={Boolean(current)}
            busy={saveOutcome.isPending}
            onChange={setForm}
            onSubmit={() => saveOutcome.mutate()}
          />
          {saveOutcome.isError && (
            <p className="vm-error-text">
              {presentError(saveOutcome.error).description}
            </p>
          )}
          <div className="vm-r9-revisions">
            <h3>Revision history</h3>
            {outcomes.data.revisions.map((item) => (
              <article key={item.outcomeId} className="vm-r9-revision">
                <strong>Revision {item.revisionNumber}</strong>
                <span>{formatTimestamp(item.recordedAt)}</span>
                <p>{item.finalConclusion}</p>
                {item.correctionReason && (
                  <small>{item.correctionReason}</small>
                )}
              </article>
            ))}
          </div>
          <small>{outcomes.data.safetyNotice}</small>
        </div>
      </div>

      <div className="vm-card">
        <header className="vm-card__header">
          <div>
            <h2>Model and Evidence Provenance</h2>
            <p>
              Trace provider, model version, input quality and explanations.
            </p>
          </div>
        </header>
        <div className="vm-card__body">
          {provenance.data.length ? (
            provenance.data.map((item) => (
              <article key={item.analysisId} className="vm-r9-provenance">
                <div>
                  <strong>
                    {item.modelName} {item.modelVersion}
                  </strong>
                  <StatusBadge status={item.synthetic ? "mock" : "provider"} />
                </div>
                <p>
                  {item.providerName} - {item.status} - input{" "}
                  {item.inputQuality}
                </p>
                <small>
                  Analysis {shortReference(item.analysisId, "AI")} - study{" "}
                  {shortReference(item.studyId, "ECG")} - v{item.recordVersion}
                </small>
              </article>
            ))
          ) : (
            <EmptyState
              title="No model provenance"
              description="No persisted ECG AI analysis has been recorded for this case."
            />
          )}
          <small>
            Model outputs are scores and attention aids, not diagnoses or
            validated clinical probabilities.
          </small>
        </div>
      </div>

      <div className="vm-card vm-r9-export">
        <header className="vm-card__header">
          <div>
            <h2>Research Export</h2>
            <p>Pseudonymized research-use package for this selected case.</p>
          </div>
          <button
            className="vm-button"
            onClick={() => exportMutation.mutate()}
            disabled={exportMutation.isPending}
          >
            <Download size={15} aria-hidden />
            {exportMutation.isPending ? "Generating" : "Generate"}
          </button>
        </header>
        <div className="vm-card__body">
          {exportMutation.isError && (
            <p className="vm-error-text">
              {presentError(exportMutation.error).description}
            </p>
          )}
          {exportResult ? (
            <div className="vm-r9-current">
              <StatusBadge status={exportResult.status} />
              <p>
                {exportResult.rowCount} row - schema{" "}
                {exportResult.schemaVersion}
              </p>
              <p>
                Checksum <code>{exportResult.checksumSha256}</code>
              </p>
              <pre className="vm-r9-csv">{exportResult.contentCsv}</pre>
              <small>{exportResult.safetyNotice}</small>
            </div>
          ) : (
            <EmptyState
              title="No export generated in this session"
              description="Exports exclude direct patient identifiers and preserve provenance and missing-data semantics."
            />
          )}
        </div>
      </div>
    </section>
  );
}

function OutcomeForm({
  value,
  correcting,
  busy,
  onChange,
  onSubmit,
}: {
  value: OutcomeFormState;
  correcting: boolean;
  busy: boolean;
  onChange: (value: OutcomeFormState) => void;
  onSubmit: () => void;
}) {
  const update = (key: keyof OutcomeFormState, next: string) =>
    onChange({ ...value, [key]: next });
  const disabled =
    busy ||
    !value.final_conclusion.trim() ||
    (correcting && !value.correction_reason.trim());
  return (
    <form
      className="vm-r9-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <label>
        <span>Outcome type</span>
        <input
          value={value.outcome_type}
          onChange={(event) => update("outcome_type", event.target.value)}
        />
      </label>
      <label>
        <span>Outcome timestamp</span>
        <input
          type="datetime-local"
          value={value.outcome_timestamp.slice(0, 16)}
          onChange={(event) =>
            update(
              "outcome_timestamp",
              new Date(event.target.value).toISOString(),
            )
          }
        />
      </label>
      <label className="vm-r9-form__wide">
        <span>Final physician-documented conclusion</span>
        <textarea
          value={value.final_conclusion}
          onChange={(event) => update("final_conclusion", event.target.value)}
        />
      </label>
      <label>
        <span>Disposition</span>
        <input
          value={value.disposition}
          onChange={(event) => update("disposition", event.target.value)}
        />
      </label>
      <label>
        <span>Destination</span>
        <input
          value={value.destination}
          onChange={(event) => update("destination", event.target.value)}
        />
      </label>
      {correcting && (
        <label className="vm-r9-form__wide">
          <span>Correction reason</span>
          <textarea
            value={value.correction_reason}
            onChange={(event) =>
              update("correction_reason", event.target.value)
            }
          />
        </label>
      )}
      <button className="vm-button" type="submit" disabled={disabled}>
        <Save size={15} aria-hidden />
        {correcting ? "Save correction" : "Record outcome"}
      </button>
    </form>
  );
}

function cleanPayload(value: OutcomeFormState): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(value)
      .filter(([key, item]) => key !== "correction_reason" || item.trim())
      .map(([key, item]) => [key, item.trim() ? item : null]),
  );
}
