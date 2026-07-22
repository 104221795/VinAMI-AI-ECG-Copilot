"use client";

import { useMemo, useState } from "react";
import type {
  ClinicianTroponinReviewView,
  RepeatTroponinRequestView,
  TroponinResultView,
  TroponinWorkspaceView,
} from "@web/entities/troponin/model";
import { EmptyState } from "@vinami/ui";
import { formatTimestamp } from "@web/shared/formatting";
import { viAction, viClinicalTerm, viStatus } from "@web/shared/locale/vi";

const fmtTime = (value: string | null) =>
  value ? formatTimestamp(value) : "Chưa có thời gian";
const label = (value: unknown) =>
  typeof value === "string" && value ? viClinicalTerm(value) : "Chưa rõ";

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
    if (!response.ok)
      throw new Error("Không thể làm mới bằng chứng xét nghiệm.");
    setValue((await response.json()) as TroponinWorkspaceView);
  }

  return (
    <div className="vm-troponin-workspace">
      <div className="vm-section-heading">
        <div>
          <p className="vm-eyebrow">Bằng chứng xét nghiệm</p>
          <h2>Troponin nối tiếp</h2>
          <p>
            Bằng chứng xét nghiệm dạng số với thông tin xét nghiệm, nguồn dữ
            liệu và provenance khi hiệu chỉnh.
          </p>
        </div>
        <div className="vm-case-header">
          <button className="vm-button" onClick={() => setPanel("import")}>
            Nạp kết quả mô phỏng
          </button>
          <button
            className="vm-button vm-button--primary"
            onClick={() => setPanel("manual")}
          >
            Ghi kết quả
          </button>
        </div>
      </div>
      <div className="vm-safety-note" role="note">
        <strong>Cần bác sĩ diễn giải.</strong> Không gian này không tạo chẩn
        đoán nhồi máu cơ tim cấp, không quyết định hướng xử trí và không chọn
        điều trị.
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
            setMessage("Đã ghi kết quả Troponin kèm provenance nguồn.");
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
              "Đã nạp kết quả xét nghiệm mô phỏng tại chỗ. Đây không phải kết nối LIS thật.",
            );
          }}
        />
      )}

      {!latest ? (
        <EmptyState
          title="Chưa có kết quả Troponin"
          description="Ghi kết quả có cấu trúc hoặc dùng bộ kết nối xét nghiệm mô phỏng tại chỗ."
        />
      ) : (
        <>
          <section className="vm-card">
            <div className="vm-card__body">
              <div className="vm-panel-toolbar">
                <div>
                  <p className="vm-eyebrow">Kết quả mới nhất</p>
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
                  <dt>Thời điểm lấy mẫu</dt>
                  <dd>{fmtTime(latest.specimen_collected_at)}</dd>
                  <dt>Thời điểm trả kết quả</dt>
                  <dd>{fmtTime(latest.resulted_at)}</dd>
                  <dt>Chất lượng</dt>
                  <dd>
                    {latest.quality_flags.length
                      ? latest.quality_flags.map(label).join(", ")
                      : "Không ghi nhận cờ kỹ thuật"}
                  </dd>
                  <dt>Giới hạn tham chiếu</dt>
                  <dd>
                    {latest.reference_limit_value
                      ? `${latest.reference_limit_value} ${latest.reference_limit_unit}`
                      : "Chưa cung cấp"}
                  </dd>
                  <dt>Nguồn</dt>
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
                  <p className="vm-eyebrow">Bằng chứng nối tiếp</p>
                  <h3>Xu hướng theo thời điểm lấy mẫu</h3>
                </div>
                <span>{value.effective_results.length} kết quả hiệu lực</span>
              </div>
              {points ? (
                <svg
                  className="vm-trop-chart"
                  viewBox="0 0 700 180"
                  role="img"
                  aria-label="Giá trị Troponin theo thời điểm lấy mẫu"
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
                  Hiện chỉ có một kết quả. Chưa thể tính thay đổi nối tiếp và
                  không suy đoán kết quả nền.
                </p>
              )}
              <ResultTable results={value.effective_results} />
            </div>
          </section>

          <section className="vm-card">
            <div className="vm-card__body">
              <p className="vm-eyebrow">Thay đổi định lượng</p>
              <h3>Delta giữa các mẫu liên tiếp tương thích</h3>
              {lastDelta ? (
                <div className="vm-trop-delta">
                  <div>
                    <span>Thay đổi tuyệt đối</span>
                    <strong>
                      {lastDelta.absolute_change ?? "Không khả dụng"}{" "}
                      {lastDelta.normalized_unit ?? ""}
                    </strong>
                  </div>
                  <div>
                    <span>Thay đổi tương đối</span>
                    <strong>
                      {lastDelta.relative_change_percent
                        ? `${lastDelta.relative_change_percent}%`
                        : "Không khả dụng"}
                    </strong>
                  </div>
                  <div>
                    <span>Khoảng cách lấy mẫu</span>
                    <strong>
                      {Math.round(lastDelta.specimen_interval_seconds / 60)} min
                    </strong>
                  </div>
                  <div>
                    <span>Mức tương thích</span>
                    <strong>{label(lastDelta.compatibility_status)}</strong>
                  </div>
                </div>
              ) : (
                <p className="vm-inline-empty">
                  Cần kết quả thứ hai tương thích về mặt kỹ thuật.
                </p>
              )}
              <p className="vm-model-warning">
                Thay đổi Troponin dạng số - cần bác sĩ diễn giải.
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
                <p className="vm-eyebrow">Xét nghiệm và tham chiếu</p>
                <h3>{latest.assay_code}</h3>
                <dl className="vm-definition-list">
                  <dt>Chất phân tích</dt>
                  <dd>{label(latest.analyte)}</dd>
                  <dt>Nhóm xét nghiệm</dt>
                  <dd>{label(latest.assay_category)}</dd>
                  <dt>Nhà sản xuất</dt>
                  <dd>{latest.manufacturer}</dd>
                  <dt>Nền tảng</dt>
                  <dd>{latest.platform}</dd>
                  <dt>Phiên bản xét nghiệm</dt>
                  <dd>{latest.assay_version}</dd>
                  <dt>Chuẩn hóa</dt>
                  <dd>
                    {latest.normalized_value ?? "Không khả dụng"}{" "}
                    {latest.normalized_unit ?? ""}
                  </dd>
                  <dt>Chuyển đổi đơn vị</dt>
                  <dd>
                    {label(latest.conversion_status)} ·{" "}
                    {latest.conversion_version}
                  </dd>
                  <dt>Nguồn tham chiếu</dt>
                  <dd>{latest.reference_limit_source ?? "Chưa cung cấp"}</dd>
                </dl>
              </div>
            </section>
            <section className="vm-card">
              <div className="vm-card__body">
                <p className="vm-eyebrow">Nguồn xét nghiệm</p>
                <h3>Nạp dữ liệu và provenance</h3>
                <p>
                  <strong>Chỉ tại chỗ/mô phỏng.</strong> Chưa cấu hình kết nối
                  LIS thật.
                </p>
                <dl className="vm-definition-list">
                  <dt>Kết quả nguồn</dt>
                  <dd>
                    <code>{latest.source_result_id}</code>
                  </dd>
                  <dt>Người ghi nhận</dt>
                  <dd>{label(latest.recorded_by_role)}</dd>
                  <dt>Độ mới dữ liệu</dt>
                  <dd>{fmtTime(value.data_freshness)}</dd>
                  <dt>Job nạp dữ liệu</dt>
                  <dd>{value.import_jobs.length}</dd>
                </dl>
              </div>
            </section>
          </div>

          <section className="vm-card">
            <div className="vm-card__body">
              <div className="vm-panel-toolbar">
                <div>
                  <p className="vm-eyebrow">Lịch sử đầy đủ</p>
                  <h3>Kết quả và hiệu chỉnh</h3>
                </div>
                <div className="vm-case-header">
                  <button
                    className="vm-button"
                    onClick={() => setPanel("amend")}
                  >
                    Hiệu chỉnh kết quả mới nhất
                  </button>
                  <button
                    className="vm-button"
                    onClick={() => setPanel("review")}
                  >
                    Ghi rà soát của bác sĩ
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
                      "Đã ghi hiệu chỉnh. Kết quả gốc vẫn nằm trong lịch sử đầy đủ.",
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
                      "Đã ghi rà soát của bác sĩ; không thực hiện chẩn đoán hoặc chuyển hướng xử trí.",
                    );
                  }}
                />
              )}
            </div>
          </section>
          <div className="vm-trop-columns">
            <section className="vm-card">
              <div className="vm-card__body">
                <p className="vm-eyebrow">Bác sĩ rà soát</p>
                <h3>
                  {value.clinician_reviews.length
                    ? `${value.clinician_reviews.length} bản ghi rà soát bất biến`
                    : "Chờ rà soát"}
                </h3>
                <p>
                  Rà soát chỉ ghi nhận bằng chứng và giới hạn dữ liệu. Nó không
                  chẩn đoán AMI và không đổi quy trình lâm sàng.
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
                        "Phiên bản rà soát đã hiệu chỉnh hiện là bản hiệu lực.",
                      );
                    }}
                  />
                )}
              </div>
            </section>
            <section className="vm-card">
              <div className="vm-card__body">
                <p className="vm-eyebrow">Lặp lại xét nghiệm</p>
                <h3>
                  {value.repeat_measurement_requests.length
                    ? `${value.repeat_measurement_requests.length} yêu cầu`
                    : "Chưa có yêu cầu"}
                </h3>
                <p>
                  Yêu cầu chỉ được tạo khi bác sĩ thao tác rõ ràng; hệ thống
                  không tự suy đoán ngưỡng thời gian.
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
            <th>Thời điểm lấy mẫu</th>
            <th>Giá trị</th>
            <th>Trạng thái</th>
            <th>Xét nghiệm</th>
            <th>Nguồn</th>
            {showHistory && <th>Lịch sử</th>}
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
                    ? `Hiệu chỉnh ${result.supersedes_result_id.slice(0, 8)}`
                    : "Bản gốc"}
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
  return `${field ? `${field}: ` : ""}${detail}${problem?.correlation_id ? ` Mã tương quan: ${problem.correlation_id}` : ""}`;
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
      <h4>Lịch sử rà soát</h4>
      <ul>
        {reviews.map((review) => (
          <li key={review.review_id}>
            <strong>{label(review.review_status)}</strong> ·{" "}
            {fmtTime(review.recorded_at)}
            {review.supersedes_review_id
              ? " · phiên bản hiệu chỉnh"
              : " · bản gốc"}
          </li>
        ))}
      </ul>
      {latest && (
        <button className="vm-button" type="button" onClick={onCorrect}>
          Hiệu chỉnh rà soát hiện tại
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
      setError("correction_reason: Cần nhập lý do hiệu chỉnh.");
      return;
    }
    if (!window.confirm("Tạo một phiên bản rà soát hiệu chỉnh bất biến?"))
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
          "Không thể ghi phiên bản rà soát hiệu chỉnh.",
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
      <h4 id="review-correction-title">Hiệu chỉnh rà soát của bác sĩ</h4>
      <p>
        Bản gốc: {label(review.review_status)} ·{" "}
        {review.note ?? "Không có ghi chú"}
      </p>
      <label className="vm-field">
        Trạng thái rà soát hiệu chỉnh
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
        Đã ghi nhận không tương thích kỹ thuật
      </label>
      <label>
        <input
          type="checkbox"
          name="quality"
          defaultChecked={review.quality_limitation_acknowledged}
        />{" "}
        Đã ghi nhận giới hạn chất lượng
      </label>
      <label className="vm-field">
        Ghi chú hiệu chỉnh
        <textarea name="note" rows={3} defaultValue={review.note ?? ""} />
      </label>
      <label className="vm-field">
        Lý do hiệu chỉnh
        <textarea
          name="correction_reason"
          rows={2}
          required
          aria-describedby="correction-reason-help"
        />
      </label>
      <p id="correction-reason-help">
        Bản rà soát gốc vẫn được giữ trong lịch sử; thao tác này tạo phiên bản
        mới.
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
          Hủy
        </button>
        <button className="vm-button vm-button--primary" disabled={busy}>
          {busy ? "Đang lưu..." : "Xác nhận hiệu chỉnh"}
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
      !window.confirm(
        `Xác nhận "${viAction(action)}" cho yêu cầu lặp lại xét nghiệm này?`,
      )
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
          "Không thể chuyển trạng thái yêu cầu lặp lại xét nghiệm.",
        ),
      );
      setBusy(null);
      return;
    }
    setCompleteId(null);
    setCancelId(null);
    await onDone(
      `Đã ${viAction(action).toLowerCase()} yêu cầu lặp lại xét nghiệm.`,
    );
    setBusy(null);
  }
  if (!requests.length) return null;
  return (
    <div className="vm-trop-review-history">
      <h4>Vòng đời yêu cầu</h4>
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
              <strong>{label(request.status)}</strong> · Phiên bản{" "}
              {request.record_version}
            </p>
            <dl className="vm-definition-list">
              <dt>Kết quả nguồn</dt>
              <dd>
                <code>{request.source_result_id}</code>
              </dd>
              <dt>Lý do</dt>
              <dd>{request.reason}</dd>
              <dt>Đã yêu cầu</dt>
              <dd>{fmtTime(request.requested_at)}</dd>
              <dt>Đã ghi nhận</dt>
              <dd>
                {request.acknowledged_at
                  ? fmtTime(request.acknowledged_at)
                  : "Chưa có"}
              </dd>
              <dt>Hoàn tất</dt>
              <dd>
                {request.completed_at
                  ? fmtTime(request.completed_at)
                  : "Chưa có"}
              </dd>
              <dt>Hủy</dt>
              <dd>{request.cancellation_reason ?? "Chưa hủy"}</dd>
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
                    Ghi nhận
                  </button>
                )}
                <button
                  type="button"
                  className="vm-button"
                  disabled={busy !== null}
                  onClick={() => setCompleteId(request.request_id)}
                >
                  Hoàn tất
                </button>
                <button
                  type="button"
                  className="vm-button"
                  disabled={busy !== null}
                  onClick={() => setCancelId(request.request_id)}
                >
                  Hủy
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
                    setError("completed_result_id: Chọn một kết quả sau đó.");
                    return;
                  }
                  void transition(request, "complete", {
                    completed_result_id: selected,
                  });
                }}
              >
                <label className="vm-field">
                  Kết quả hoàn tất (backend xác thực)
                  <select name="completed_result_id" required defaultValue="">
                    <option value="" disabled>
                      Chọn kết quả
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
                  Xác nhận hoàn tất
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
                    setError("reason: Cần nhập lý do hủy.");
                    return;
                  }
                  void transition(request, "cancel", { reason });
                }}
              >
                <label className="vm-field">
                  Lý do hủy
                  <input name="reason" required />
                </label>
                <button
                  className="vm-button vm-button--primary"
                  disabled={busy !== null}
                >
                  Xác nhận hủy
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
        ? "Siêu dữ liệu xét nghiệm nhập tay"
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
      setError(await problemMessage(response, "Không thể ghi kết quả."));
      setBusy(false);
      return;
    }
    await onDone();
  }
  return (
    <form className="vm-card vm-action-panel" onSubmit={submit}>
      <div className="vm-card__body">
        <h3>Ghi kết quả Troponin có cấu trúc</h3>
        <div className="vm-form-grid">
          <label className="vm-field">
            Xét nghiệm
            <select name="assay" required defaultValue="">
              <option value="" disabled>
                Chọn xét nghiệm
              </option>
              <option value="DEMO-HS-CTNI-01">Minh họa hs-cTnI</option>
              <option value="DEMO-HS-CTNT-01">Minh họa hs-cTnT</option>
            </select>
          </label>
          <label className="vm-field">
            Giá trị
            <input name="value" inputMode="decimal" required />
          </label>
          <label className="vm-field">
            Đơn vị
            <select name="unit" required defaultValue="">
              <option value="" disabled>
                Chọn đơn vị
              </option>
              <option>ng/L</option>
              <option>pg/mL</option>
              <option>ng/mL</option>
            </select>
          </label>
          <label className="vm-field">
            Thời điểm lấy mẫu
            <input name="collected" type="datetime-local" required />
          </label>
          <label className="vm-field">
            Giới hạn tham chiếu trên (tùy chọn)
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
            Hủy
          </button>
          <button className="vm-button vm-button--primary" disabled={busy}>
            {busy ? "Đang ghi..." : "Xác nhận và ghi"}
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
          "Không thể hoàn tất nạp kết quả mô phỏng.",
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
        <h3>Nạp kết quả mô phỏng tại chỗ</h3>
        <p>
          Đây không phải kết nối LIS thật và không dùng endpoint HL7/FHIR thật.
        </p>
        <label className="vm-field">
          Kịch bản
          <select name="scenario">
            <option value="success">Kết quả độc lập thành công</option>
            <option value="preliminary">Vòng đời: kết quả sơ bộ</option>
            <option value="final">Vòng đời: kết quả cuối cùng</option>
            <option value="amended">Vòng đời: kết quả hiệu chỉnh</option>
            <option value="duplicate-preliminary">
              Gửi trùng kết quả sơ bộ
            </option>
            <option value="duplicate-final">Gửi trùng kết quả cuối cùng</option>
            <option value="duplicate-amended">
              Gửi trùng kết quả hiệu chỉnh
            </option>
            <option value="missing-reference-limit">
              Thiếu giới hạn tham chiếu
            </option>
            <option value="retry-success">Lỗi để minh họa thử lại</option>
            <option value="timeout">Quá thời gian</option>
          </select>
          {error && (
            <p className="vm-inline-notice" role="alert">
              {error}
            </p>
          )}
        </label>
        <div className="vm-case-header">
          <button type="button" className="vm-button" onClick={onClose}>
            Hủy
          </button>
          <button className="vm-button vm-button--primary" disabled={busy}>
            Chạy nạp mô phỏng
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
      <h3>Ghi rà soát bằng chứng của bác sĩ</h3>
      <label>
        <input type="checkbox" name="incompatible" /> Đã ghi nhận không tương
        thích kỹ thuật
      </label>
      <label>
        <input type="checkbox" name="quality" /> Đã ghi nhận giới hạn chất lượng
      </label>
      <label>
        <input type="checkbox" name="repeat" /> Yêu cầu lặp lại xét nghiệm
      </label>
      <label className="vm-field">
        Lý do lặp lại
        <input name="reason" />
      </label>
      <label className="vm-field">
        Ghi chú tùy chọn
        <textarea name="note" rows={3} />
      </label>
      <div className="vm-case-header">
        <button type="button" className="vm-button" onClick={onClose}>
          Hủy
        </button>
        <button className="vm-button vm-button--primary">
          Xác nhận rà soát
        </button>
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
        `${problem?.detail ?? "Không thể ghi hiệu chỉnh."}${problem?.correlation_id ? ` Mã tương quan: ${problem.correlation_id}` : ""}`,
      );
      return;
    }
    await onDone();
  }
  return (
    <form className="vm-action-panel" onSubmit={submit}>
      <h3>Hiệu chỉnh kết quả bất biến</h3>
      <p>
        Bản gốc vẫn được giữ lại. Thao tác này tạo một bản thay thế có liên kết.
      </p>
      <label className="vm-field">
        Giá trị hiệu chỉnh
        <input
          name="value"
          inputMode="decimal"
          defaultValue={latest.original_value}
          required
        />
      </label>
      <label className="vm-field">
        Lý do hiệu chỉnh
        <textarea name="reason" rows={3} required />
      </label>
      {error && (
        <p className="vm-inline-notice" role="alert">
          {error}
        </p>
      )}
      <div className="vm-case-header">
        <button type="button" className="vm-button" onClick={onClose}>
          Hủy
        </button>
        <button className="vm-button vm-button--primary">
          Xác nhận hiệu chỉnh
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
