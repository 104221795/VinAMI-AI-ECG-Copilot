"use client";

import { useState, useTransition } from "react";
import {
  Activity,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  FileInput,
  Info,
  RefreshCw,
  ShieldAlert,
  Upload,
} from "lucide-react";
import { Badge, ClinicalCard, EmptyState } from "@vinami/ui";
import type { ECGWaveform } from "@vinami/api-client";
import type { ECGWorkspaceView } from "@web/entities/ecg/model";
import { createBrowserApiClient } from "@web/shared/api/browser";
import { presentError } from "@web/shared/errors/presentation";
import { formatTimestamp, shortReference } from "@web/shared/formatting";
import {
  viAction,
  viClinicalTerm,
  viSafetyNotice,
  viStatus,
} from "@web/shared/locale/vi";
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
    "Bác sĩ yêu cầu lặp lại ECG để rà soát kỹ thuật",
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
      setMessage("Đã nạp ECG 12 chuyển đạo mô phỏng và đánh giá chất lượng.");
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
      setMessage(`${viClinicalTerm(sourceType)} đã được lưu kèm nguồn gốc.`);
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
      setMessage("Đã lưu yêu cầu DICOM bệnh viện mô phỏng.");
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
      setMessage("Đã thử nạp lại an toàn và không tạo job trùng.");
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
      setMessage("Đã lưu so sánh ECG nối tiếp kỹ thuật để bác sĩ rà soát.");
    });
  }

  function recordComparisonReview(comparisonId: string, version: number) {
    if (!comparisonReview.trim()) return;
    if (!window.confirm("Ghi nhận rà soát so sánh ECG động của bác sĩ?"))
      return;
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
      setMessage("Đã ghi nhận rà soát so sánh ECG động của bác sĩ.");
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
      setMessage("Đã đặt nhắc lặp lại ECG theo yêu cầu bác sĩ.");
    });
  }

  function transitionReminder(
    reminder: ECGWorkspaceView["reminders"][number],
    action: "acknowledge" | "complete" | "cancel",
  ) {
    if (
      !window.confirm(
        `Xác nhận thao tác "${viAction(action)}" cho nhắc lại ECG?`,
      )
    )
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
            action === "cancel" ? "Bác sĩ hủy nhắc việc minh họa" : null,
        },
        crypto.randomUUID(),
      );
      await refresh();
      setMessage(
        `Đã ghi nhận thao tác ${viClinicalTerm(action)} cho nhắc ECG.`,
      );
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
      setMessage("Đã hoàn tất phân tích mô phỏng dùng cho nghiên cứu.");
    });
  }

  function recordReview() {
    if (!value.currentStudy || !reviewSummary.trim()) return;
    if (!window.confirm("Ghi nhận rà soát ECG của bác sĩ vào audit trail?"))
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
      setMessage("Đã ghi nhận rà soát của bác sĩ kèm nguồn gốc mô hình.");
    });
  }

  return (
    <section className="vm-ecg-workspace" aria-labelledby="ecg-workspace-title">
      <div className="vm-section-heading">
        <div className="vm-source-action-card">
          <span className="vm-eyebrow">R3 ECG Intelligence</span>
          <h2 id="ecg-workspace-title">Không gian rà soát ECG</h2>
        </div>
        <Badge tone="warning">Nguyên mẫu nghiên cứu</Badge>
      </div>
      <div className="vm-safety-banner" role="note">
        <ShieldAlert size={18} aria-hidden="true" />
        <span>
          ECG và điểm mô hình không thể loại trừ nhồi máu cơ tim cấp hoặc kích
          hoạt phòng can thiệp. Cần bác sĩ rà soát và đối chiếu lâm sàng.
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
      {value.technicalWarnings.length ? (
        <div className="vm-technical-warning" role="status">
          <Info size={17} aria-hidden="true" />
          <div>
            <strong>Đã tải một phần dữ liệu ECG</strong>
            {value.technicalWarnings.map((warning) => (
              <p key={warning}>{warning}</p>
            ))}
          </div>
        </div>
      ) : null}

      {!value.currentStudy ? (
        <div className="vm-section-stack">
          <EmptyState
            title="Ca này chưa có ECG"
            description="Nạp dạng sóng mô phỏng xác định để kiểm thử luồng lâm sàng R3."
            action={
              <button
                className="vm-button vm-button--primary"
                disabled={isPending}
                onClick={addDemoStudy}
              >
                <Upload size={16} aria-hidden="true" />
                {isPending ? "Đang xử lý..." : "Nạp ECG 12 chuyển đạo mô phỏng"}
              </button>
            }
          />
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
            aria-label="Trạng thái ECG hiện tại"
          >
            <StatusMetric
              label="Lần đo"
              value={value.currentStudy.studyReference}
            />
            <StatusMetric
              label="Chất lượng"
              value={viStatus(value.quality?.status ?? "pending")}
            />
            <StatusMetric
              label="Thời điểm đo"
              value={formatTimestamp(value.currentStudy.acquisitionAt)}
            />
            <StatusMetric
              label="Phân tích"
              value={viStatus(latestAnalysis?.status ?? "not_requested")}
            />
          </section>

          <ClinicalCard title="Dạng sóng 12 chuyển đạo">
            <div className="vm-panel-toolbar">
              <p>
                {value.currentStudy.samplingRateHz ?? "-"} Hz |{" "}
                {value.currentStudy.durationSeconds ?? "-"} s |{" "}
                {value.currentStudy.amplitudeUnit ?? "chưa có đơn vị"}
              </p>
              <button
                className="vm-button vm-button--secondary"
                disabled={isPending}
                onClick={addDemoStudy}
              >
                <Upload size={15} aria-hidden="true" /> Thêm ECG nối tiếp
              </button>
            </div>
            {value.waveform ? (
              <WaveformGrid value={value.waveform} />
            ) : (
              <p className="vm-inline-empty">
                Lần đo này chưa có dạng sóng có cấu trúc.
              </p>
            )}
          </ClinicalCard>

          <div className="vm-layout-split vm-layout-split--ecg">
            <ClinicalCard title="Chất lượng kỹ thuật">
              <QualityPanel value={value} />
            </ClinicalCard>
            <ClinicalCard title="Bằng chứng nối tiếp">
              <SerialPanel value={value} />
            </ClinicalCard>
          </div>

          <AIPathPanel
            value={value}
            latestAnalysis={latestAnalysis}
            latestInterpretation={latestInterpretation}
          />

          <ClinicalCard title="Kết quả đa nhãn có AI hỗ trợ">
            {latestAnalysis ? (
              <AnalysisPanel
                value={latestAnalysis}
                suppress={value.quality?.suppressScoreEmphasis ?? false}
              />
            ) : value.currentStudy.waveformAvailable ? (
              <div className="vm-inline-action">
                <BrainCircuit size={22} aria-hidden="true" />
                <div>
                  <strong>Chưa có phân tích mô hình cho lần đo hiện tại</strong>
                  <p>
                    Chạy provider mô phỏng xác định để kiểm tra hợp đồng đầu ra
                    chuẩn hóa.
                  </p>
                </div>
                <button
                  className="vm-button vm-button--primary"
                  disabled={isPending}
                  onClick={requestAnalysis}
                >
                  Chạy phân tích nghiên cứu
                </button>
              </div>
            ) : (
              <p className="vm-inline-empty">
                Phân tích dạng sóng tự động không khả dụng với ECG chỉ có tài
                liệu.
              </p>
            )}
          </ClinicalCard>

          <ClinicalCard
            title={
              value.currentStudy.waveformAvailable
                ? "Bác sĩ rà soát ECG"
                : "Bác sĩ rà soát tài liệu"
            }
          >
            <div className="vm-review-layout">
              <div>
                <label className="vm-field-label" htmlFor="ecg-review-summary">
                  Tóm tắt rà soát có cấu trúc
                </label>
                <textarea
                  id="ecg-review-summary"
                  value={reviewSummary}
                  onChange={(event) => setReviewSummary(event.target.value)}
                  placeholder="Ghi nhận diễn giải của bác sĩ và đối chiếu lâm sàng"
                  rows={4}
                />
                <button
                  className="vm-button vm-button--primary"
                  disabled={isPending || !reviewSummary.trim()}
                  onClick={recordReview}
                >
                  <CheckCircle2 size={16} aria-hidden="true" /> Ghi nhận rà soát
                  của bác sĩ
                </button>
              </div>
              <div className="vm-review-history">
                <h3>Lịch sử rà soát</h3>
                {value.interpretations.length ? (
                  value.interpretations.map((item) => (
                    <article key={item.interpretationId}>
                      <strong>{viStatus(item.status)}</strong>
                      <p>{item.summary}</p>
                      <small>
                        {item.actorRole} | {formatTimestamp(item.recordedAt)}
                      </small>
                    </article>
                  ))
                ) : (
                  <p>Chưa ghi nhận diễn giải của bác sĩ.</p>
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
      ? `Bộ cung cấp mô phỏng: ${latestAnalysis.providerName}`
      : `Bộ cung cấp mô hình: ${latestAnalysis.providerName}`
    : "Chưa có kết quả từ bộ cung cấp mô hình";
  const steps = [
    {
      label: "Đã ghi nhận ECG",
      status: study ? "available" : "missing",
      detail: study
        ? `${study.studyReference} - ${formatTimestamp(study.acquisitionAt)}`
        : "Chưa chọn lần đo ECG.",
      source: "Lần đo ECG",
      tone: "evidence",
    },
    {
      label: "Kiểm tra chất lượng kỹ thuật",
      status: value.quality?.status ?? "pending",
      detail: value.quality
        ? `${value.quality.engineVersion} - ${value.quality.reasonCodes.map(viClinicalTerm).join(", ") || "không có mã lý do"}`
        : "Chưa ghi nhận đánh giá chất lượng.",
      source: "Bằng chứng do máy tạo",
      tone: "machine",
    },
    {
      label: "Suy luận mô hình",
      status: machineStatus,
      detail: latestAnalysis
        ? `${latestAnalysis.modelName} ${latestAnalysis.modelVersion} - ${latestAnalysis.completedAt ? formatTimestamp(latestAnalysis.completedAt) : "chưa có thời điểm hoàn tất"}`
        : "Chỉ chạy phân tích nghiên cứu khi có dữ liệu dạng sóng.",
      source: providerLabel,
      tone: "machine",
    },
    {
      label: "Kết quả và giải thích mô hình",
      status: latestAnalysis?.explanationStatus ?? "pending",
      detail: latestAnalysis
        ? `${latestAnalysis.findings.length} điểm mô hình. Điểm số không phải xác suất bệnh.`
        : "Chưa ghi nhận điểm mô hình hoặc tham chiếu giải thích.",
      source: "Nhận định ECG có AI hỗ trợ",
      tone: "machine",
    },
    {
      label: "Bác sĩ rà soát ECG",
      status: latestInterpretation ? latestInterpretation.status : "pending",
      detail: latestInterpretation
        ? latestInterpretation.summary
        : "Cần bác sĩ diễn giải trước mọi thẩm quyền lâm sàng.",
      source: "Diễn giải do bác sĩ ghi nhận",
      tone: "physician",
    },
    {
      label: "Tổng hợp bằng chứng và quyết định",
      status: latestInterpretation ? "under review" : "not started",
      detail:
        "Không gian tổng hợp lâm sàng là nơi tổng hợp bằng chứng, đánh giá và ghi nhận quyết định của bác sĩ.",
      source: "Không gian tổng hợp lâm sàng",
      tone: "authority",
    },
  ];
  return (
    <ClinicalCard title="Luồng ECG có AI hỗ trợ">
      <div
        className="vm-ai-path"
        aria-label="Luồng bằng chứng ECG có AI hỗ trợ"
      >
        {steps.map((step) => (
          <article
            className={`vm-ai-step vm-ai-step--${step.tone}`}
            key={step.label}
          >
            <span
              className={`vm-status-pill vm-status-pill--${step.status.replaceAll(" ", "-")}`}
            >
              {viStatus(step.status)}
            </span>
            <h3>{step.label}</h3>
            <p>{step.detail}</p>
            <small>{step.source}</small>
          </article>
        ))}
      </div>
      <p className="vm-safety-note">
        Bằng chứng ECG do máy tạo được tách riêng với diễn giải của bác sĩ và
        quyết định do bác sĩ xác nhận. AI không thể tự tạo công việc, cảnh báo,
        chuyển trạng thái quy trình hoặc thẩm quyền can thiệp.
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
    <ClinicalCard title="Nguồn ECG và tích hợp">
      <div className="vm-source-actions">
        <div className="vm-source-action-card">
          <span className="vm-field-label">Tệp ECG định dạng bệnh viện</span>
          <input
            aria-label="Tệp ECG DICOM, XML hoặc PDF"
            type="file"
            accept=".dcm,.dicom,.xml,.pdf,application/dicom,application/xml,application/pdf"
            onChange={(event) => onFile(event.target.files?.[0] ?? null)}
          />
          <button
            className="vm-button vm-button--secondary"
            disabled={!uploadFile || isPending}
            onClick={onUpload}
          >
            <FileInput size={15} aria-hidden="true" /> Nạp tệp đã chọn
          </button>
        </div>
        <div className="vm-source-action-card">
          <span className="vm-field-label">Bộ kết nối bệnh viện mô phỏng</span>
          <button
            className="vm-button vm-button--secondary"
            disabled={isPending}
            onClick={() => onImport("R3-DICOM-001")}
          >
            Nạp DICOM mô phỏng
          </button>
          <button
            className="vm-button vm-button--secondary"
            disabled={isPending}
            onClick={() => onImport("R3-DICOM-RETRY")}
          >
            Kiểm thử lỗi quá thời gian
          </button>
        </div>
      </div>
      <div className="vm-connector-grid">
        {value.connectors.map((connector) => (
          <article key={connector.connectorId} className="vm-integration-item">
            <div>
              <strong>{connector.displayName}</strong>
              <Badge tone={connector.available ? "success" : "critical"}>
                {connector.available ? "Có sẵn" : "Không khả dụng"}
              </Badge>
            </div>
            <p>{connector.detail}</p>
            <small>
              {viClinicalTerm(connector.connectorType)} |{" "}
              {connector.profile ?? "Chưa có hồ sơ"} |{" "}
              {connector.version ?? "Chưa rõ phiên bản"}
            </small>
          </article>
        ))}
        {!value.connectors.length ? (
          <p className="vm-inline-empty">
            Chưa có registry bộ kết nối hoặc chưa đăng ký connector mô phỏng.
            Vẫn có thể nạp ECG tại chỗ để demo.
          </p>
        ) : null}
      </div>
      <div className="vm-ingestion-list" aria-label="Các job nạp ECG">
        {value.ingestionJobs.length ? (
          value.ingestionJobs.map((job) => (
            <article key={job.jobId} className="vm-integration-item">
              <div>
                <strong>{viClinicalTerm(job.sourceType)}</strong>
                <Badge
                  tone={
                    job.status === "completed"
                      ? "success"
                      : job.status === "failed"
                        ? "critical"
                        : "warning"
                  }
                >
                  {viStatus(job.status)}
                </Badge>
              </div>
              <p>
                {job.connectorId ?? "Tải lên tại chỗ"} | yêu cầu lúc{" "}
                {formatTimestamp(job.requestedAt)}
              </p>
              <small>
                Bộ phân tích {job.parser ?? "đang chờ"}{" "}
                {job.parserVersion ?? ""} | số lần thử lại {job.retryCount}
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
                  <RefreshCw size={14} aria-hidden="true" /> Thử lại an toàn
                </button>
              ) : null}
              <details>
                <summary>Chi tiết kỹ thuật</summary>
                <code>{job.correlationId}</code>
                {job.warnings.map((warning) => (
                  <p key={warning}>{viSafetyNotice(warning)}</p>
                ))}
              </details>
            </article>
          ))
        ) : (
          <p className="vm-inline-empty">
            Chưa có job nạp ECG nào được yêu cầu.
          </p>
        )}
      </div>
      {value.currentStudy?.sourceType === "pdf_document" ? (
        <div className="vm-pdf-state">
          <div className="vm-safety-banner" role="note">
            Chỉ có tài liệu nguồn. Dạng sóng có cấu trúc và phân tích dạng sóng
            tự động không khả dụng.
          </div>
          <iframe
            title="Xem trước tài liệu ECG PDF nguồn"
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
    <ClinicalCard title="So sánh ECG động">
      <p className="vm-score-explainer">
        Chỉ báo thay đổi ECG về mặt kỹ thuật - cần bác sĩ diễn giải trước khi
        dùng trong quyết định lâm sàng.
      </p>
      <div className="vm-comparison-controls">
        <label className="vm-field">
          <span>ECG nền</span>
          <select
            value={baselineStudyId}
            onChange={(event) => onBaseline(event.target.value)}
          >
            <option value="">Chọn ECG nền</option>
            {value.studies.map((study) => (
              <option key={study.studyId} value={study.studyId}>
                {study.studyReference} | {formatTimestamp(study.acquisitionAt)}
              </option>
            ))}
          </select>
        </label>
        <label className="vm-field">
          <span>ECG hiện tại</span>
          <select
            value={currentStudyId}
            onChange={(event) => onCurrent(event.target.value)}
          >
            <option value="">Chọn ECG hiện tại</option>
            {value.studies.map((study) => (
              <option key={study.studyId} value={study.studyId}>
                {study.studyReference} | {formatTimestamp(study.acquisitionAt)}
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
          So sánh tín hiệu kỹ thuật
        </button>
      </div>
      {comparison ? (
        <div className="vm-section-stack">
          <div className="vm-comparison-summary">
            <StatusMetric
              label="Khả năng so sánh"
              value={viStatus(comparison.comparabilityStatus)}
            />
            <StatusMetric
              label="Tương thích điểm mô hình"
              value={viStatus(comparison.scoreCompatibility)}
            />
            <StatusMetric label="Chính sách" value={comparison.policyVersion} />
          </div>
          {comparison.comparabilityReasons.length ? (
            <div className="vm-safety-banner" role="status">
              {comparison.comparabilityReasons.map(viClinicalTerm).join(" | ")}
            </div>
          ) : null}
          <div className="vm-r18-review-note" role="note">
            <Info size={17} aria-hidden="true" />
            <span>{comparison.reviewRecommendation}</span>
          </div>
          <div className="vm-r18-signal-grid">
            <IndicatorDigest
              title="Nhịp và tần số"
              indicators={comparison.rhythmChangeIndicators}
              empty="Không phát hiện thay đổi proxy nhịp/tần số theo chính sách demo."
            />
            <IndicatorDigest
              title="ST/T proxy"
              indicators={comparison.stTChangeIndicators}
              empty="Không phát hiện thay đổi ST/T proxy theo chính sách demo."
            />
          </div>
          {comparison.signalFeatureDeltas.length ? (
            <FeatureDeltaGrid values={comparison.signalFeatureDeltas} />
          ) : null}
          <div
            className="vm-dynamic-waveforms"
            aria-label="Dạng sóng ECG nối tiếp đã đồng bộ"
          >
            <div>
              <h3>ECG nền</h3>
              {baselineWaveform ? (
                <WaveformGrid value={baselineWaveform} />
              ) : (
                <p>Chạy so sánh để xem dạng sóng có cấu trúc.</p>
              )}
            </div>
            <div>
              <h3>ECG hiện tại</h3>
              {currentWaveform ? (
                <WaveformGrid value={currentWaveform} />
              ) : (
                <p>Dạng sóng có cấu trúc không khả dụng.</p>
              )}
            </div>
          </div>
          {comparison.leadComparisons.length ? (
            <div className="vm-table-scroll">
              <table>
                <caption>
                  Chỉ số kỹ thuật theo từng chuyển đạo, không phải chẩn đoán
                </caption>
                <thead>
                  <tr>
                    <th>Chuyển đạo</th>
                    <th>Độ tương đồng</th>
                    <th>Khác biệt chuẩn hóa</th>
                    <th>Lệch nền</th>
                    <th>Căn chỉnh</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.leadComparisons.map((lead) => (
                    <tr key={lead.leadName}>
                      <th>{lead.leadName}</th>
                      <td>{lead.waveformSimilarity.toFixed(3)}</td>
                      <td>{lead.normalizedDifference.toFixed(3)}</td>
                      <td>{lead.baselineShiftIndicator.toFixed(3)}</td>
                      <td>{viStatus(lead.sampleAlignmentStatus)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {comparison.scoreEvolution.length ? (
            <div className="vm-score-evolution">
              <h3>Diễn tiến điểm mô hình tương thích</h3>
              {comparison.scoreEvolution.map((score) => (
                <div key={score.findingCode}>
                  <strong>{score.findingCode}</strong>
                  <span>
                    {score.previousScore.toFixed(3)}
                    {" -> "}
                    {score.currentScore.toFixed(3)}
                  </span>
                  <small>
                    Delta {score.absoluteDelta.toFixed(3)} |{" "}
                    {viStatus(score.compatibilityStatus)}
                  </small>
                </div>
              ))}
            </div>
          ) : (
            <p>
              Không hiển thị delta điểm mô hình khi provenance mô hình hoặc tiền
              xử lý không tương thích.
            </p>
          )}
          {comparison.technicalChangeIndicators.length ? (
            <div className="vm-r18-technical-list">
              <h3>Tóm tắt kỹ thuật từ backend</h3>
              <ul>
                {comparison.technicalChangeIndicators.map((indicator) => (
                  <li key={indicator}>{viClinicalTerm(indicator)}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <label className="vm-field-label" htmlFor="dynamic-review">
            Bác sĩ rà soát so sánh
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
            Ghi nhận rà soát của bác sĩ
          </button>
        </div>
      ) : (
        <p className="vm-inline-empty">
          Chọn hai lần đo ECG có cấu trúc để đánh giá khả năng so sánh kỹ thuật.
        </p>
      )}
    </ClinicalCard>
  );
}

function IndicatorDigest({
  title,
  indicators,
  empty,
}: {
  title: string;
  indicators: string[];
  empty: string;
}) {
  return (
    <article className="vm-r18-digest">
      <h3>{title}</h3>
      {indicators.length ? (
        <ul>
          {indicators.map((indicator) => (
            <li key={indicator}>{viClinicalTerm(indicator)}</li>
          ))}
        </ul>
      ) : (
        <p>{empty}</p>
      )}
    </article>
  );
}

function FeatureDeltaGrid({
  values,
}: {
  values: ECGWorkspaceView["comparisons"][number]["signalFeatureDeltas"];
}) {
  return (
    <div className="vm-r18-feature-grid" aria-label="R18 signal feature deltas">
      {values.map((feature) => (
        <article
          className={`vm-r18-feature vm-r18-feature--${feature.status}`}
          key={feature.featureName}
        >
          <span>{featureLabel(feature.displayLabel)}</span>
          <strong>{featureValue(feature.currentValue, feature.unit)}</strong>
          <small>
            Baseline {featureValue(feature.previousValue, feature.unit)} | Δ{" "}
            {featureValue(feature.absoluteDelta, feature.unit)}
          </small>
          <em>{featureStatus(feature.status)}</em>
        </article>
      ))}
    </div>
  );
}

function featureValue(value: number | null, unit: string | null): string {
  if (value === null || Number.isNaN(value)) return "không đủ dữ liệu";
  const rounded = Math.abs(value) >= 10 ? value.toFixed(1) : value.toFixed(3);
  return unit ? `${rounded} ${unit}` : rounded;
}

function featureStatus(value: string): string {
  if (value === "changed") return "Có thay đổi proxy";
  if (value === "stable") return "Ổn định theo policy demo";
  if (value === "incompatible") return "Không tương thích kỹ thuật";
  return "Không đủ dữ liệu";
}

function featureLabel(value: string): string {
  const labels: Record<string, string> = {
    "Global amplitude proxy": "Biên độ toàn cục proxy",
    "Heart-rate proxy": "Tần số tim proxy",
    "QRS width proxy": "Độ rộng QRS proxy",
    "Rhythm regularity proxy": "Độ đều nhịp proxy",
    "ST-level morphology proxy": "ST-level proxy",
    "Sampling rate": "Tần số lấy mẫu",
    "T-wave morphology proxy": "Sóng T proxy",
  };
  return labels[value] ?? value;
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
    <ClinicalCard title="Nhắc lại ECG">
      <div className="vm-inline-action">
        <Clock3 size={22} aria-hidden="true" />
        <div className="vm-field">
          <label className="vm-field-label" htmlFor="repeat-reason">
            Lý do
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
          Hẹn sau 30 phút
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
                {viStatus(reminder.status)}
              </Badge>
            </div>
            <p>
              Hạn {formatTimestamp(reminder.dueAt)} |{" "}
              {viClinicalTerm(reminder.origin)} | người yêu cầu{" "}
              {reminder.requestedByRole}
            </p>
            {reminder.completedAt ? (
              <small>Hoàn tất {formatTimestamp(reminder.completedAt)}</small>
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
                    Ghi nhận
                  </button>
                ) : null}
                <button
                  className="vm-button vm-button--secondary"
                  disabled={value.studies.length < 2}
                  onClick={() => onTransition(reminder, "complete")}
                >
                  Hoàn tất bằng ECG sau đó
                </button>
                <button
                  className="vm-button vm-button--secondary"
                  onClick={() => onTransition(reminder, "cancel")}
                >
                  Hủy
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
  if (!value.quality) return <p>Chưa có đánh giá chất lượng.</p>;
  return (
    <div className="vm-quality-panel">
      <div
        className={`vm-quality-mark vm-quality-mark--${value.quality.status}`}
      >
        <Activity size={18} aria-hidden="true" />{" "}
        {viStatus(value.quality.status)}
      </div>
      <dl className="vm-definition-list">
        <dt>Bộ đánh giá</dt>
        <dd>{value.quality.engineVersion}</dd>
        <dt>Chuyển đạo ảnh hưởng</dt>
        <dd>{value.quality.affectedLeads.join(", ") || "Không phát hiện"}</dd>
        <dt>Mã lý do</dt>
        <dd>
          {value.quality.reasonCodes.map(viClinicalTerm).join(", ") ||
            "Không có"}
        </dd>
      </dl>
    </div>
  );
}

function SerialPanel({ value }: { value: ECGWorkspaceView }) {
  return (
    <div>
      <strong>{value.studies.length} lần đo ECG</strong>
      <ol className="vm-serial-list">
        {[...value.studies].reverse().map((study, index) => (
          <li key={study.studyId}>
            <span>{index === 0 ? "Hiện tại" : `Trước đó ${index}`}</span>
            <strong>{study.studyReference}</strong>
            <small>
              {formatTimestamp(study.acquisitionAt)} |{" "}
              {viStatus(study.qualityStatus)}
            </small>
          </li>
        ))}
      </ol>
      {value.comparisons.length ? (
        <p>{value.comparisons.length} so sánh kỹ thuật đã ghi nhận.</p>
      ) : (
        <p>So sánh sẽ có sau khi yêu cầu một cặp ECG nối tiếp.</p>
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
          <span>Mô hình</span>
          <strong>{value.modelName}</strong>
        </div>
        <div>
          <span>Phiên bản</span>
          <strong>{value.modelVersion}</strong>
        </div>
        <div>
          <span>Bộ cung cấp</span>
          <strong>{value.providerName}</strong>
        </div>
        <div>
          <span>Lần chạy</span>
          <strong>{shortReference(value.analysisId, "AI")}</strong>
        </div>
      </div>
      <p className="vm-score-explainer">
        Năm đầu ra mô hình độc lập, xếp từ cao xuống thấp. Vượt ngưỡng chỉ đánh
        dấu ưu tiên rà soát, không phải chẩn đoán và điểm số không cần cộng lại
        bằng 1.
      </p>
      {suppress ? (
        <div className="vm-safety-banner vm-safety-banner--critical">
          Chất lượng kỹ thuật không đạt nên không nhấn mạnh điểm số bình thường.
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
              <span>{viClinicalTerm(finding.label)}</span>
            </div>
            <div
              className="vm-score-track"
              role="progressbar"
              aria-label={`${finding.code} điểm mô hình ${finding.score.toFixed(3)}`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(finding.score * 100)}
              aria-valuetext={`${(finding.score * 100).toFixed(1)} phần trăm; ${finding.thresholdMet ? "trên" : "dưới"} ngưỡng mô hình`}
            >
              <span style={{ width: `${finding.score * 100}%` }} />
              {finding.threshold !== null ? (
                <i style={{ left: `${finding.threshold * 100}%` }} />
              ) : null}
            </div>
            <div className="vm-finding-value">
              <strong>{finding.score.toFixed(3)}</strong>
              <span>
                {finding.thresholdMet ? "Cần rà soát" : "Dưới ngưỡng"}
              </span>
            </div>
          </li>
        ))}
      </ol>
      {value.explanationStatus === "available" && value.explanationArtifactId ? (
        <section className="vm-gradcam-showcase" aria-label="Grad-CAM model-attention artifact">
          <div className="vm-gradcam-copy">
            <BrainCircuit size={19} aria-hidden="true" />
            <div>
              <strong>Grad-CAM model-attention artifact</strong>
              <p>
                Hình ảnh này chỉ cho thấy vùng tín hiệu ảnh hưởng tới điểm model.
                Không diễn giải như chẩn đoán, xác suất bệnh hoặc định vị tổn thương.
              </p>
            </div>
          </div>
          <figure className="vm-gradcam-frame">
            <img
              src={`/api/backend/api/v1/ecg-analyses/${value.analysisId}/explanation`}
              alt="Grad-CAM attention overlay for ECG model review"
            />
            <figcaption>
              Artifact đã lưu: {shortReference(value.explanationArtifactId, "EXP")}
            </figcaption>
          </figure>
        </section>
      ) : (
        <div className="vm-gradcam-unavailable" role="note">
          <Info size={16} aria-hidden="true" />
          <span>Chưa có Grad-CAM artifact cho lần phân tích này.</span>
        </div>
      )}
      <p className="vm-model-warning">
        {[value.safetyNotice, ...value.warnings].map(viSafetyNotice).join(" ")}
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
