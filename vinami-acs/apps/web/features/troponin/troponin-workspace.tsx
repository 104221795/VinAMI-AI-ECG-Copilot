"use client";

import { useMemo, useState } from "react";
import type {
  ClinicianTroponinReviewView,
  RepeatTroponinRequestView,
  TroponinResultView,
  TroponinWorkspaceView,
} from "@web/entities/troponin/model";

const fmtTime = (value: string | null) =>
  value
    ? new Intl.DateTimeFormat("en-GB", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "Not available";
const label = (value: unknown) =>
  typeof value === "string" && value ? value.replaceAll("_", " ") : "Unknown";

export function TroponinWorkspace({
  caseId,
  initialValue,
}: {
  caseId: string;
  initialValue: TroponinWorkspaceView;
}) {
  const [value, setValue] = useState(initialValue);
  const [panel, setPanel] = useState<
    "none" | "manual" | "import" | "review" | "amend" | "correction"
  >("none");
  const [message, setMessage] = useState<string | null>(null);
  const latest = value.latest_result;
  const lastDelta = value.deltas.at(-1) ?? null;
  const points = useMemo(
    () => trendPoints(value.effective_results),
    [value.effective_results],
  );

  async function refresh() {
    const response = await fetch(
      `/api/backend/api/v1/clinical-cases/${caseId}/troponin-workspace`,
      { cache: "no-store" },
    );
    if (!response.ok) throw new Error("Could not refresh laboratory evidence.");
    setValue((await response.json()) as TroponinWorkspaceView);
  }

  return (
    <div className="vm-troponin-workspace">
      <div className="vm-section-heading">
        <div>
          <p className="vm-eyebrow">Laboratory evidence</p>
          <h2>Serial troponin</h2>
          <p>
            Numerical laboratory evidence with assay, source and amendment
            provenance.
          </p>
        </div>
        <div className="vm-case-header">
          <button className="vm-button" onClick={() => setPanel("import")}>
            Import mock result
          </button>
          <button
            className="vm-button vm-button--primary"
            onClick={() => setPanel("manual")}
          >
            Record result
          </button>
        </div>
      </div>
      <div className="vm-safety-note" role="note">
        <strong>Clinician interpretation required.</strong> This workspace does
        not produce an acute myocardial infarction diagnosis or disposition and
        does not select a pathway or treatment.
      </div>
      {message && (
        <div className="vm-inline-notice" role="status">
          {message}
        </div>
      )}
      {panel === "manual" && (
        <ManualForm
          caseId={caseId}
          caseVersion={value.case_version}
          onClose={() => setPanel("none")}
          onDone={async () => {
            await refresh();
            setPanel("none");
            setMessage("Troponin result recorded with source provenance.");
          }}
        />
      )}
      {panel === "import" && (
        <ImportForm
          caseId={caseId}
          caseVersion={value.case_version}
          onClose={() => setPanel("none")}
          onDone={async () => {
            await refresh();
            setPanel("none");
            setMessage(
              "Local mock laboratory import completed. This is not a live LIS connection.",
            );
          }}
        />
      )}

      {!latest ? (
        <section className="vm-card vm-empty-state">
          <div className="vm-card__body">
            <h3>No troponin results</h3>
            <p>
              Record a structured result or use the deterministic local/mock
              laboratory connector.
            </p>
          </div>
        </section>
      ) : (
        <>
          <section className="vm-card">
            <div className="vm-card__body">
              <div className="vm-panel-toolbar">
                <div>
                  <p className="vm-eyebrow">Latest result</p>
                  <h3>{latest.assay_display_name}</h3>
                </div>
                <span className="vm-badge">{label(latest.result_status)}</span>
              </div>
              <div className="vm-trop-latest">
                <div>
                  <strong>{latest.original_value}</strong>
                  <span>{latest.original_unit}</span>
                </div>
                <dl>
                  <dt>Specimen collected</dt>
                  <dd>{fmtTime(latest.specimen_collected_at)}</dd>
                  <dt>Resulted</dt>
                  <dd>{fmtTime(latest.resulted_at)}</dd>
                  <dt>Quality</dt>
                  <dd>
                    {latest.quality_flags.length
                      ? latest.quality_flags.map(label).join(", ")
                      : "No technical flag reported"}
                  </dd>
                  <dt>Reference limit</dt>
                  <dd>
                    {latest.reference_limit_value
                      ? `${latest.reference_limit_value} ${latest.reference_limit_unit}`
                      : "Not supplied"}
                  </dd>
                  <dt>Source</dt>
                  <dd>
                    {label(latest.source_type)} · {latest.source_system}
                  </dd>
                </dl>
              </div>
            </div>
          </section>

          <section className="vm-card">
            <div className="vm-card__body">
              <div className="vm-panel-toolbar">
                <div>
                  <p className="vm-eyebrow">Serial evidence</p>
                  <h3>Specimen-time trend</h3>
                </div>
                <span>
                  {value.effective_results.length} effective result
                  {value.effective_results.length === 1 ? "" : "s"}
                </span>
              </div>
              {points ? (
                <svg
                  className="vm-trop-chart"
                  viewBox="0 0 700 180"
                  role="img"
                  aria-label="Troponin values ordered by specimen collection time"
                >
                  <polyline
                    points={points}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                  />
                  <line x1="36" y1="150" x2="680" y2="150" />
                </svg>
              ) : (
                <p className="vm-inline-empty">
                  One result only. Serial numerical change is unavailable; no
                  baseline is inferred.
                </p>
              )}
              <ResultTable results={value.effective_results} />
            </div>
          </section>

          <section className="vm-card">
            <div className="vm-card__body">
              <p className="vm-eyebrow">Numerical change</p>
              <h3>Delta between consecutive compatible specimens</h3>
              {lastDelta ? (
                <div className="vm-trop-delta">
                  <div>
                    <span>Absolute change</span>
                    <strong>
                      {lastDelta.absolute_change ?? "Unavailable"}{" "}
                      {lastDelta.normalized_unit ?? ""}
                    </strong>
                  </div>
                  <div>
                    <span>Relative change</span>
                    <strong>
                      {lastDelta.relative_change_percent
                        ? `${lastDelta.relative_change_percent}%`
                        : "Unavailable"}
                    </strong>
                  </div>
                  <div>
                    <span>Specimen interval</span>
                    <strong>
                      {Math.round(lastDelta.specimen_interval_seconds / 60)} min
                    </strong>
                  </div>
                  <div>
                    <span>Compatibility</span>
                    <strong>{label(lastDelta.compatibility_status)}</strong>
                  </div>
                </div>
              ) : (
                <p className="vm-inline-empty">
                  A second technically compatible result is required.
                </p>
              )}
              <p className="vm-model-warning">
                Numerical troponin change - clinician interpretation required.
              </p>
              {lastDelta?.incompatibility_reasons.map((reason) => (
                <p className="vm-inline-notice" key={reason}>
                  {reason}
                </p>
              ))}
            </div>
          </section>

          <div className="vm-trop-columns">
            <section className="vm-card">
              <div className="vm-card__body">
                <p className="vm-eyebrow">Assay and reference</p>
                <h3>{latest.assay_code}</h3>
                <dl className="vm-definition-list">
                  <dt>Analyte</dt>
                  <dd>{label(latest.analyte)}</dd>
                  <dt>Category</dt>
                  <dd>{label(latest.assay_category)}</dd>
                  <dt>Manufacturer</dt>
                  <dd>{latest.manufacturer}</dd>
                  <dt>Platform</dt>
                  <dd>{latest.platform}</dd>
                  <dt>Assay version</dt>
                  <dd>{latest.assay_version}</dd>
                  <dt>Normalization</dt>
                  <dd>
                    {latest.normalized_value ?? "Unavailable"}{" "}
                    {latest.normalized_unit ?? ""}
                  </dd>
                  <dt>Conversion</dt>
                  <dd>
                    {label(latest.conversion_status)} ·{" "}
                    {latest.conversion_version}
                  </dd>
                  <dt>Reference source</dt>
                  <dd>{latest.reference_limit_source ?? "Not supplied"}</dd>
                </dl>
              </div>
            </section>
            <section className="vm-card">
              <div className="vm-card__body">
                <p className="vm-eyebrow">Laboratory source</p>
                <h3>Import and provenance</h3>
                <p>
                  <strong>Local/mock only.</strong> No live LIS connection is
                  configured.
                </p>
                <dl className="vm-definition-list">
                  <dt>Source result</dt>
                  <dd>
                    <code>{latest.source_result_id}</code>
                  </dd>
                  <dt>Recorded by</dt>
                  <dd>{label(latest.recorded_by_role)}</dd>
                  <dt>Data freshness</dt>
                  <dd>{fmtTime(value.data_freshness)}</dd>
                  <dt>Import jobs</dt>
                  <dd>{value.import_jobs.length}</dd>
                </dl>
              </div>
            </section>
          </div>

          <section className="vm-card">
            <div className="vm-card__body">
              <div className="vm-panel-toolbar">
                <div>
                  <p className="vm-eyebrow">Complete history</p>
                  <h3>Results and amendments</h3>
                </div>
                <div className="vm-case-header">
                  <button
                    className="vm-button"
                    onClick={() => setPanel("amend")}
                  >
                    Amend latest result
                  </button>
                  <button
                    className="vm-button"
                    onClick={() => setPanel("review")}
                  >
                    Record clinician review
                  </button>
                </div>
              </div>
              <ResultTable results={value.result_history} showHistory />
              {panel === "amend" && (
                <AmendmentForm
                  latest={latest}
                  onClose={() => setPanel("none")}
                  onDone={async () => {
                    await refresh();
                    setPanel("none");
                    setMessage(
                      "Amendment recorded. The original result remains in complete history.",
                    );
                  }}
                />
              )}
              {panel === "review" && (
                <ReviewForm
                  caseId={caseId}
                  caseVersion={value.case_version}
                  latest={latest}
                  onClose={() => setPanel("none")}
                  onDone={async () => {
                    await refresh();
                    setPanel("none");
                    setMessage(
                      "Clinician review recorded; no diagnostic or pathway action was performed.",
                    );
                  }}
                />
              )}
            </div>
          </section>
          <div className="vm-trop-columns">
            <section className="vm-card">
              <div className="vm-card__body">
                <p className="vm-eyebrow">Clinician review</p>
                <h3>
                  {value.clinician_reviews.length
                    ? `${value.clinician_reviews.length} immutable review record(s)`
                    : "Awaiting review"}
                </h3>
                <p>
                  Review acknowledges evidence and limitations only. It cannot
                  diagnose AMI or change the clinical workflow.
                </p>
                <ReviewHistory
                  reviews={value.clinician_reviews}
                  latest={value.latest_clinician_review}
                  onCorrect={() => setPanel("correction")}
                />
                {panel === "correction" && value.latest_clinician_review && (
                  <ReviewCorrectionForm
                    caseId={caseId}
                    caseVersion={value.case_version}
                    review={value.latest_clinician_review}
                    onClose={() => setPanel("none")}
                    onDone={async () => {
                      await refresh();
                      setPanel("none");
                      setMessage(
                        "A corrected immutable review revision is now effective.",
                      );
                    }}
                  />
                )}
              </div>
            </section>
            <section className="vm-card">
              <div className="vm-card__body">
                <p className="vm-eyebrow">Repeat measurement</p>
                <h3>
                  {value.repeat_measurement_requests.length
                    ? `${value.repeat_measurement_requests.length} request(s)`
                    : "No request"}
                </h3>
                <p>
                  A request is created only by an explicit clinician action; no
                  timing threshold is inferred.
                </p>
                <RepeatRequestPanel
                  requests={value.repeat_measurement_requests}
                  results={value.effective_results}
                  onDone={async (notice) => {
                    await refresh();
                    setMessage(notice);
                  }}
                />
              </div>
            </section>
          </div>
        </>
      )}
    </div>
  );
}

function ResultTable({
  results,
  showHistory = false,
}: {
  results: TroponinResultView[];
  showHistory?: boolean;
}) {
  return (
    <div className="vm-table-scroll">
      <table className="vm-table">
        <thead>
          <tr>
            <th>Specimen time</th>
            <th>Value</th>
            <th>Status</th>
            <th>Assay</th>
            <th>Source</th>
            {showHistory && <th>History</th>}
          </tr>
        </thead>
        <tbody>
          {results.map((result) => (
            <tr key={result.result_id}>
              <td>{fmtTime(result.specimen_collected_at)}</td>
              <td className="vm-tabular">
                {result.original_value} {result.original_unit}
              </td>
              <td>{label(result.result_status)}</td>
              <td>{result.assay_code}</td>
              <td>{label(result.source_type)}</td>
              {showHistory && (
                <td>
                  {result.supersedes_result_id
                    ? `Amends ${result.supersedes_result_id.slice(0, 8)}`
                    : "Original"}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type Problem = {
  detail?: string;
  correlation_id?: string;
  errors?: Array<{ field?: string; code?: string }>;
};

async function problemMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  const problem = (await response.json().catch(() => null)) as Problem | null;
  const field = problem?.errors?.[0]?.field;
  const detail = problem?.detail ?? fallback;
  return `${field ? `${field}: ` : ""}${detail}${problem?.correlation_id ? ` Correlation: ${problem.correlation_id}` : ""}`;
}

function ReviewHistory({
  reviews,
  latest,
  onCorrect,
}: {
  reviews: ClinicianTroponinReviewView[];
  latest: ClinicianTroponinReviewView | null;
  onCorrect: () => void;
}) {
  if (!reviews.length) return null;
  return (
    <div className="vm-trop-review-history">
      <h4>Review history</h4>
      <ul>
        {reviews.map((review) => (
          <li key={review.review_id}>
            <strong>{review.review_status}</strong> ·{" "}
            {fmtTime(review.recorded_at)}
            {review.supersedes_review_id
              ? " · corrected revision"
              : " · original"}
          </li>
        ))}
      </ul>
      {latest && (
        <button className="vm-button" type="button" onClick={onCorrect}>
          Correct current review
        </button>
      )}
    </div>
  );
}

function ReviewCorrectionForm({
  caseId,
  caseVersion,
  review,
  onClose,
  onDone,
}: {
  caseId: string;
  caseVersion: number;
  review: ClinicianTroponinReviewView;
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const reason = String(data.get("correction_reason") ?? "").trim();
    if (!reason) {
      setError("correction_reason: A correction reason is required.");
      return;
    }
    if (!window.confirm("Create an immutable corrected review revision?"))
      return;
    setBusy(true);
    setError(null);
    const response = await fetch(
      `/api/backend/api/v1/clinical-cases/${caseId}/troponin-reviews/${review.review_id}/corrections`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          correction_reason: reason,
          referenced_result_ids: review.referenced_result_ids,
          review_status: data.get("review_status"),
          incompatibility_acknowledged: data.has("incompatible"),
          quality_limitation_acknowledged: data.has("quality"),
          repeat_measurement_requested: review.repeat_measurement_requested,
          repeat_measurement_reason: review.repeat_measurement_reason,
          corrected_note: data.get("note") || null,
          occurred_at: new Date().toISOString(),
          expected_case_version: caseVersion,
          expected_review_version: review.record_version,
        }),
      },
    );
    if (!response.ok) {
      setError(
        await problemMessage(
          response,
          "The corrected review could not be recorded.",
        ),
      );
      setBusy(false);
      return;
    }
    await onDone();
  }
  return (
    <form
      className="vm-action-panel"
      onSubmit={submit}
      aria-labelledby="review-correction-title"
    >
      <h4 id="review-correction-title">Correct clinician review</h4>
      <p>
        Original: {review.review_status} · {review.note ?? "No note"}
      </p>
      <label className="vm-field">
        Corrected review status
        <input
          name="review_status"
          defaultValue={review.review_status}
          required
        />
      </label>
      <label>
        <input
          type="checkbox"
          name="incompatible"
          defaultChecked={review.incompatibility_acknowledged}
        />{" "}
        Technical incompatibility acknowledged
      </label>
      <label>
        <input
          type="checkbox"
          name="quality"
          defaultChecked={review.quality_limitation_acknowledged}
        />{" "}
        Quality limitation acknowledged
      </label>
      <label className="vm-field">
        Corrected note
        <textarea name="note" rows={3} defaultValue={review.note ?? ""} />
      </label>
      <label className="vm-field">
        Correction reason
        <textarea
          name="correction_reason"
          rows={2}
          required
          aria-describedby="correction-reason-help"
        />
      </label>
      <p id="correction-reason-help">
        The original review remains in history; this creates a new revision.
      </p>
      {error && (
        <p className="vm-inline-notice" role="alert">
          {error}
        </p>
      )}
      <div className="vm-case-header">
        <button
          type="button"
          className="vm-button"
          disabled={busy}
          onClick={onClose}
        >
          Cancel
        </button>
        <button className="vm-button vm-button--primary" disabled={busy}>
          {busy ? "Saving…" : "Confirm correction"}
        </button>
      </div>
    </form>
  );
}

function RepeatRequestPanel({
  requests,
  results,
  onDone,
}: {
  requests: RepeatTroponinRequestView[];
  results: TroponinResultView[];
  onDone: (notice: string) => Promise<void>;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [completeId, setCompleteId] = useState<string | null>(null);
  const [cancelId, setCancelId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function transition(
    request: RepeatTroponinRequestView,
    action: "acknowledge" | "complete" | "cancel",
    payload: Record<string, string | null> = {},
  ) {
    if (
      !window.confirm(`Confirm ${action} for this repeat measurement request?`)
    )
      return;
    setBusy(`${request.request_id}-${action}`);
    setError(null);
    const response = await fetch(
      `/api/backend/api/v1/repeat-troponin-requests/${request.request_id}/${action}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          expected_version: request.record_version,
          ...payload,
        }),
      },
    );
    if (!response.ok) {
      setError(
        await problemMessage(
          response,
          "The repeat-measurement transition could not be completed.",
        ),
      );
      setBusy(null);
      return;
    }
    setCompleteId(null);
    setCancelId(null);
    await onDone(`Repeat measurement request ${action}d.`);
    setBusy(null);
  }
  if (!requests.length) return null;
  return (
    <div className="vm-trop-review-history">
      <h4>Request lifecycle</h4>
      {error && (
        <p className="vm-inline-notice" role="alert">
          {error}
        </p>
      )}
      {requests.map((request) => {
        const open =
          request.status === "requested" || request.status === "acknowledged";
        const candidates = results.filter(
          (result) => result.result_id !== request.source_result_id,
        );
        return (
          <article key={request.request_id} className="vm-repeat-request">
            <p>
              <strong>{label(request.status)}</strong> · Version{" "}
              {request.record_version}
            </p>
            <dl className="vm-definition-list">
              <dt>Source result</dt>
              <dd>
                <code>{request.source_result_id}</code>
              </dd>
              <dt>Reason</dt>
              <dd>{request.reason}</dd>
              <dt>Requested</dt>
              <dd>{fmtTime(request.requested_at)}</dd>
              <dt>Acknowledged</dt>
              <dd>
                {request.acknowledged_at
                  ? fmtTime(request.acknowledged_at)
                  : "Not yet"}
              </dd>
              <dt>Completed</dt>
              <dd>
                {request.completed_at
                  ? fmtTime(request.completed_at)
                  : "Not yet"}
              </dd>
              <dt>Cancellation</dt>
              <dd>{request.cancellation_reason ?? "Not cancelled"}</dd>
            </dl>
            {open && (
              <div className="vm-case-header">
                {request.status === "requested" && (
                  <button
                    type="button"
                    className="vm-button"
                    disabled={busy !== null}
                    onClick={() => transition(request, "acknowledge")}
                  >
                    Acknowledge
                  </button>
                )}
                <button
                  type="button"
                  className="vm-button"
                  disabled={busy !== null}
                  onClick={() => setCompleteId(request.request_id)}
                >
                  Complete
                </button>
                <button
                  type="button"
                  className="vm-button"
                  disabled={busy !== null}
                  onClick={() => setCancelId(request.request_id)}
                >
                  Cancel
                </button>
              </div>
            )}
            {completeId === request.request_id && (
              <form
                className="vm-action-panel"
                onSubmit={(event) => {
                  event.preventDefault();
                  const selected = String(
                    new FormData(event.currentTarget).get(
                      "completed_result_id",
                    ) ?? "",
                  );
                  if (!selected) {
                    setError(
                      "completed_result_id: Select a subsequent result.",
                    );
                    return;
                  }
                  void transition(request, "complete", {
                    completed_result_id: selected,
                  });
                }}
              >
                <label className="vm-field">
                  Completion result (validated by backend)
                  <select name="completed_result_id" required defaultValue="">
                    <option value="" disabled>
                      Select result
                    </option>
                    {candidates.map((result) => (
                      <option value={result.result_id} key={result.result_id}>
                        {result.original_value} {result.original_unit} ·{" "}
                        {fmtTime(result.specimen_collected_at)}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  className="vm-button vm-button--primary"
                  disabled={busy !== null}
                >
                  Confirm completion
                </button>
              </form>
            )}
            {cancelId === request.request_id && (
              <form
                className="vm-action-panel"
                onSubmit={(event) => {
                  event.preventDefault();
                  const reason = String(
                    new FormData(event.currentTarget).get("reason") ?? "",
                  ).trim();
                  if (!reason) {
                    setError("reason: A cancellation reason is required.");
                    return;
                  }
                  void transition(request, "cancel", { reason });
                }}
              >
                <label className="vm-field">
                  Cancellation reason
                  <input name="reason" required />
                </label>
                <button
                  className="vm-button vm-button--primary"
                  disabled={busy !== null}
                >
                  Confirm cancellation
                </button>
              </form>
            )}
          </article>
        );
      })}
    </div>
  );
}

function ManualForm({
  caseId,
  caseVersion,
  onClose,
  onDone,
}: {
  caseId: string;
  caseVersion: number;
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const data = new FormData(event.currentTarget);
    const collected = new Date(String(data.get("collected"))).toISOString();
    const body = {
      assay_code: data.get("assay"),
      analyte:
        data.get("assay") === "DEMO-HS-CTNT-01"
          ? "cardiac_troponin_t"
          : "cardiac_troponin_i",
      value: data.get("value"),
      unit: data.get("unit"),
      specimen_type: "plasma",
      specimen_collected_at: collected,
      resulted_at: new Date().toISOString(),
      result_status: "final",
      reference_limit_value: data.get("reference") || null,
      reference_limit_unit: data.get("reference") ? data.get("unit") : null,
      reference_limit_source: data.get("reference")
        ? "Manually supplied laboratory metadata"
        : null,
      quality_flags: [],
      source_system: "manual-entry",
      source_result_id: `manual-${crypto.randomUUID()}`,
      expected_case_version: caseVersion,
    };
    const response = await fetch(
      `/api/backend/api/v1/clinical-cases/${caseId}/troponin-results`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify(body),
      },
    );
    if (!response.ok) {
      setError(
        await problemMessage(response, "The result could not be recorded."),
      );
      setBusy(false);
      return;
    }
    await onDone();
  }
  return (
    <form className="vm-card vm-action-panel" onSubmit={submit}>
      <div className="vm-card__body">
        <h3>Record structured troponin result</h3>
        <div className="vm-form-grid">
          <label className="vm-field">
            Assay
            <select name="assay" required defaultValue="">
              <option value="" disabled>
                Select assay
              </option>
              <option value="DEMO-HS-CTNI-01">Demonstration hs-cTnI</option>
              <option value="DEMO-HS-CTNT-01">Demonstration hs-cTnT</option>
            </select>
          </label>
          <label className="vm-field">
            Value
            <input name="value" inputMode="decimal" required />
          </label>
          <label className="vm-field">
            Unit
            <select name="unit" required defaultValue="">
              <option value="" disabled>
                Select unit
              </option>
              <option>ng/L</option>
              <option>pg/mL</option>
              <option>ng/mL</option>
            </select>
          </label>
          <label className="vm-field">
            Specimen collection
            <input name="collected" type="datetime-local" required />
          </label>
          <label className="vm-field">
            Upper reference limit (optional)
            <input name="reference" inputMode="decimal" />
          </label>
        </div>
        {error && (
          <p className="vm-inline-notice" role="alert">
            {error}
          </p>
        )}
        <div className="vm-case-header">
          <button type="button" className="vm-button" onClick={onClose}>
            Cancel
          </button>
          <button className="vm-button vm-button--primary" disabled={busy}>
            {busy ? "Recording…" : "Confirm and record"}
          </button>
        </div>
      </div>
    </form>
  );
}

function ImportForm({
  caseId,
  caseVersion,
  onClose,
  onDone,
}: {
  caseId: string;
  caseVersion: number;
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const data = new FormData(event.currentTarget);
    const response = await fetch(
      `/api/backend/api/v1/clinical-cases/${caseId}/troponin-imports`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          connector_id: "mock-lab-r4",
          external_reference: data.get("scenario"),
          expected_case_version: caseVersion,
        }),
      },
    );
    if (!response.ok) {
      setError(
        await problemMessage(
          response,
          "The mock import could not be completed.",
        ),
      );
      setBusy(false);
      return;
    }
    await onDone();
  }
  return (
    <form className="vm-card vm-action-panel" onSubmit={submit}>
      <div className="vm-card__body">
        <h3>Deterministic local/mock import</h3>
        <p>
          This is not a live LIS connection and does not use HL7 or FHIR
          endpoints.
        </p>
        <label className="vm-field">
          Scenario
          <select name="scenario">
            <option value="success">Successful independent result</option>
            <option value="preliminary">Lifecycle: preliminary delivery</option>
            <option value="final">Lifecycle: final delivery</option>
            <option value="amended">Lifecycle: amended delivery</option>
            <option value="duplicate-preliminary">
              Duplicate preliminary delivery
            </option>
            <option value="duplicate-final">Duplicate final delivery</option>
            <option value="duplicate-amended">
              Duplicate amended delivery
            </option>
            <option value="missing-reference-limit">
              Missing reference limit
            </option>
            <option value="retry-success">
              Failure for retry demonstration
            </option>
            <option value="timeout">Timeout</option>
          </select>
          {error && (
            <p className="vm-inline-notice" role="alert">
              {error}
            </p>
          )}
        </label>
        <div className="vm-case-header">
          <button type="button" className="vm-button" onClick={onClose}>
            Cancel
          </button>
          <button className="vm-button vm-button--primary" disabled={busy}>
            Run mock import
          </button>
        </div>
      </div>
    </form>
  );
}

function ReviewForm({
  caseId,
  caseVersion,
  latest,
  onClose,
  onDone,
}: {
  caseId: string;
  caseVersion: number;
  latest: TroponinResultView;
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await fetch(
      `/api/backend/api/v1/clinical-cases/${caseId}/troponin-reviews`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          referenced_result_ids: [latest.result_id],
          review_status: "evidence_reviewed",
          incompatibility_acknowledged: data.has("incompatible"),
          quality_limitation_acknowledged: data.has("quality"),
          repeat_measurement_requested: data.has("repeat"),
          repeat_measurement_reason: data.has("repeat")
            ? String(data.get("reason"))
            : null,
          note: data.get("note") || null,
          occurred_at: new Date().toISOString(),
          expected_case_version: caseVersion,
        }),
      },
    );
    await onDone();
  }
  return (
    <form className="vm-action-panel" onSubmit={submit}>
      <h3>Record clinician evidence review</h3>
      <label>
        <input type="checkbox" name="incompatible" /> Technical incompatibility
        acknowledged
      </label>
      <label>
        <input type="checkbox" name="quality" /> Quality limitation acknowledged
      </label>
      <label>
        <input type="checkbox" name="repeat" /> Request repeat measurement
      </label>
      <label className="vm-field">
        Reason for repeat
        <input name="reason" />
      </label>
      <label className="vm-field">
        Optional note
        <textarea name="note" rows={3} />
      </label>
      <div className="vm-case-header">
        <button type="button" className="vm-button" onClick={onClose}>
          Cancel
        </button>
        <button className="vm-button vm-button--primary">Confirm review</button>
      </div>
    </form>
  );
}

function AmendmentForm({
  latest,
  onClose,
  onDone,
}: {
  latest: TroponinResultView;
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  const [error, setError] = useState<string | null>(null);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const response = await fetch(
      `/api/backend/api/v1/troponin-results/${latest.result_id}/amendments`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          value: data.get("value"),
          unit: latest.original_unit,
          result_status: "amended",
          amendment_reason: data.get("reason"),
          resulted_at: new Date().toISOString(),
          expected_version: latest.record_version,
        }),
      },
    );
    if (!response.ok) {
      const problem = (await response.json().catch(() => null)) as {
        detail?: string;
        correlation_id?: string;
      } | null;
      setError(
        `${problem?.detail ?? "The amendment could not be recorded."}${problem?.correlation_id ? ` Correlation: ${problem.correlation_id}` : ""}`,
      );
      return;
    }
    await onDone();
  }
  return (
    <form className="vm-action-panel" onSubmit={submit}>
      <h3>Amend immutable result</h3>
      <p>
        The original remains available. This action creates a linked replacement
        record.
      </p>
      <label className="vm-field">
        Amended value
        <input
          name="value"
          inputMode="decimal"
          defaultValue={latest.original_value}
          required
        />
      </label>
      <label className="vm-field">
        Amendment reason
        <textarea name="reason" rows={3} required />
      </label>
      {error && (
        <p className="vm-inline-notice" role="alert">
          {error}
        </p>
      )}
      <div className="vm-case-header">
        <button type="button" className="vm-button" onClick={onClose}>
          Cancel
        </button>
        <button className="vm-button vm-button--primary">
          Confirm amendment
        </button>
      </div>
    </form>
  );
}

function trendPoints(results: TroponinResultView[]): string | null {
  if (results.length < 2) return null;
  const values = results.map((item) => Number(item.normalized_value));
  if (values.some(Number.isNaN)) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  return values
    .map(
      (value, index) =>
        `${36 + index * (644 / (values.length - 1))},${140 - ((value - min) / (max - min || 1)) * 110}`,
    )
    .join(" ");
}
