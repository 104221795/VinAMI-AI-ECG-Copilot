"use client";

import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Clock3, RefreshCw } from "lucide-react";
import Link from "next/link";
import {
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  OfflineState,
  StaleDataBanner,
} from "@vinami/ui";
import { createBrowserApiClient } from "@web/shared/api/browser";
import { presentError } from "@web/shared/errors/presentation";
import {
  formatDueLabel,
  formatTimestamp,
  safeDemographics,
  shortReference,
} from "@web/shared/formatting";
import {
  viClinicalLabel,
  viClinicalTerm,
  viDecisionType,
  viPriority,
  viSafetyNotice,
  viStatus,
  viTaskType,
  viWorkflowState,
} from "@web/shared/locale/vi";
import { useConnectivity } from "@web/shared/hooks/use-connectivity";
import { IntegrationStatusPanel } from "@web/features/realtime/integration-status-panel";
import { RealtimeStatus } from "@web/features/realtime/connection-status";
import { useRealtimeUpdates } from "@web/features/realtime/use-realtime-updates";
import { EvidenceStatusSummary } from "@web/features/evidence/evidence-status-summary";
import { EvidenceAutomationPanel } from "@web/features/evidence/evidence-automation-panel";
import { loadCompleteCaseWorkspaceWith } from "./data";
import type { CompleteCaseWorkspaceView } from "./model";

const text = (value: unknown, fallback = "Chưa ghi nhận") =>
  typeof value === "string" && value.length ? value : fallback;
const number = (value: unknown) => (typeof value === "number" ? value : 0);
const list = (value: unknown) => (Array.isArray(value) ? value : []);

export function CompleteCaseWorkspace({
  caseId,
  initialValue,
}: {
  caseId: string;
  initialValue: CompleteCaseWorkspaceView;
}) {
  const online = useConnectivity();
  const realtime = useRealtimeUpdates({
    caseId,
    invalidate: [
      ["r8-complete-case-workspace", caseId],
      ["r10-integration-status"],
    ],
  });
  const query = useQuery({
    queryKey: ["r8-complete-case-workspace", caseId],
    queryFn: () =>
      loadCompleteCaseWorkspaceWith(createBrowserApiClient(), caseId),
    initialData: initialValue,
    staleTime: 20_000,
    refetchInterval: 30_000,
  });
  if (!online && !query.data)
    return <OfflineState onRetry={() => query.refetch()} />;
  if (query.isLoading) return <LoadingSkeleton lines={12} />;
  if (query.isError) {
    const error = presentError(query.error);
    return (
      <ErrorState
        {...error}
        onRetry={error.retryable ? () => query.refetch() : undefined}
      />
    );
  }
  const value = query.data;
  if (!value) return null;
  const stale =
    !online || Date.now() - new Date(value.evaluated_at).getTime() > 60_000;
  const latestTroponin = value.troponin.latest_result as Record<
    string,
    unknown
  > | null;
  const latestDelta = value.troponin.latest_delta as Record<
    string,
    unknown
  > | null;
  const interpretation = value.ecg?.physician_interpretation as Record<
    string,
    unknown
  > | null;
  const analysis = value.ecg?.analysis as Record<string, unknown> | null;
  return (
    <main
      className="vm-case-workspace"
      aria-label="Không gian tổng hợp ca lâm sàng"
    >
      {stale && (
        <StaleDataBanner updatedLabel={formatTimestamp(value.evaluated_at)} />
      )}
      <RealtimeStatus
        state={realtime.state}
        lastUpdateAt={realtime.lastUpdateAt}
        notification={realtime.notification}
      />
      <header className="vm-case-workspace__header">
        <div>
          <p className="vm-eyebrow">Ca nghi hội chứng mạch vành cấp</p>
          <h1>{shortReference(value.case_id, "CASE")}</h1>
          <p>
            {value.patient_reference} ·{" "}
            {safeDemographics(value.age_band, value.sex_at_birth)} ·{" "}
            {value.location}
          </p>
          <code className="vm-raw-identifier">{value.case_id}</code>
        </div>
        <div
          className="vm-case-workspace__status"
          aria-label="Trạng thái ca và cập nhật"
        >
          <strong>{viStatus(value.case_status)}</strong>
          <span>Ưu tiên {viPriority(value.case_priority)}</span>
          <span>Cập nhật {formatTimestamp(value.last_updated_at)}</span>
          <button
            className="vm-button vm-button--secondary"
            onClick={() => query.refetch()}
            disabled={query.isFetching}
          >
            <RefreshCw size={15} aria-hidden />{" "}
            {query.isFetching ? "Đang làm mới" : "Làm mới"}
          </button>
        </div>
      </header>

      <nav
        className="vm-case-workspace__nav"
        aria-label="Điều hướng không gian ca"
      >
        <Link href={`/cases/${caseId}`} aria-current="page">
          Tổng quan
        </Link>
        <Link href={`/cases/${caseId}/documentation`}>
          Tiếp nhận / Sinh hiệu
        </Link>
        <Link href={`/cases/${caseId}/ecg`}>ECG</Link>
        <Link href={`/cases/${caseId}/troponin`}>Troponin</Link>
        <Link href={`/cases/${caseId}/clinical-reasoning`}>
          Tổng hợp lâm sàng
        </Link>
        <Link href={`/cases/${caseId}/workflow`}>Quy trình</Link>
        <Link href={`/cases/${caseId}/timeline`}>Dòng thời gian</Link>
        <Link href={`/cases/${caseId}/audit`}>Nhật ký kiểm chứng</Link>
      </nav>

      <EvidenceStatusSummary
        title="Chú ý bằng chứng"
        status={value.evidence_status}
        missingEvidence={value.missing_evidence}
        staleEvidence={value.stale_evidence}
        technicalLimits={value.technical_limits}
      />
      <EvidenceAutomationPanel automation={value.automation} />

      <div className="vm-case-workspace__grid">
        <Panel
          title="Tiếp nhận và sinh hiệu mới nhất"
          link={`/cases/${caseId}/documentation`}
          linkLabel="Mở tiếp nhận / sinh hiệu"
        >
          {value.triage ? (
            <>
              <Fact
                label="Lý do vào viện"
                value={text(value.triage.chief_complaint)}
              />
              <Fact
                label="Triệu chứng"
                value={text(value.triage.symptom_description)}
              />
              <Fact
                label="Thời điểm lâm sàng"
                value={formatTimestamp(text(value.triage.occurred_at))}
              />
              <Source value={value.triage} idKey="assessment_id" />
            </>
          ) : (
            <Empty label="Chưa có bản ghi tiếp nhận hiện hành" />
          )}
          <div className="vm-vital-compact">
            {value.vitals ? (
              list(value.vitals.measurements).map((item, index) => {
                const measurement = item as Record<string, unknown>;
                const unit = text(measurement.unit, "");
                return (
                  <span key={`${text(measurement.kind)}-${index}`}>
                    <strong>
                      <span>{formatMeasurementValue(measurement.value)}</span>
                      {unit ? <em>{unit}</em> : null}
                    </strong>
                    <small>{viClinicalLabel(text(measurement.kind))}</small>
                  </span>
                );
              })
            ) : (
              <Empty label="Chưa có bộ sinh hiệu hiện hành" />
            )}
          </div>
        </Panel>

        <Panel
          title="Bằng chứng ECG"
          link={`/cases/${caseId}/ecg`}
          linkLabel="Mở không gian ECG"
        >
          {value.ecg ? (
            <>
              <Fact label="Lần đo" value={text(value.ecg.study_reference)} />
              <Fact
                label="Chất lượng kỹ thuật"
                value={viStatus(text(value.ecg.quality_status))}
              />
              <Fact
                label="Thời điểm đo"
                value={formatTimestamp(text(value.ecg.acquisition_at))}
              />
              <Fact
                label="Nhận định ECG có AI hỗ trợ"
                value={
                  analysis
                    ? `${text(analysis.status)} · ${text(analysis.model_name)} ${text(analysis.model_version, "")}`
                    : "Chưa có kết quả mô hình"
                }
              />
              <Fact
                label="Diễn giải của bác sĩ"
                value={
                  interpretation
                    ? text(interpretation.structured_interpretation)
                    : "Chưa ghi nhận bác sĩ rà soát"
                }
              />
              <Source value={value.ecg} idKey="study_id" />
              <small>
                Đầu ra mô hình chỉ hỗ trợ quyết định, không phải chẩn đoán hoặc
                xác suất lâm sàng.
              </small>
            </>
          ) : (
            <Empty label="Chưa có bản ghi ECG hiện hành" />
          )}
        </Panel>

        <Panel
          title="Troponin nối tiếp"
          link={`/cases/${caseId}/troponin`}
          linkLabel="Mở không gian Troponin"
        >
          {latestTroponin ? (
            <>
              <Fact
                label="Kết quả mới nhất"
                value={`${text(latestTroponin.value)} ${text(latestTroponin.unit, "")}`}
              />
              <Fact
                label="Xét nghiệm"
                value={text(latestTroponin.assay_name)}
              />
              <Fact
                label="Thời điểm lấy mẫu"
                value={formatTimestamp(
                  text(latestTroponin.specimen_collected_at),
                )}
              />
              <Fact
                label="Kết quả hiệu lực"
                value={String(number(value.troponin.result_count))}
              />
              <Fact
                label="Delta mới nhất do backend tính"
                value={
                  latestDelta
                    ? `${text(latestDelta.absolute_change)} ${text(latestDelta.unit, "")} · ${text(latestDelta.compatibility_status)}`
                    : "Đang chờ kết quả nối tiếp tương thích"
                }
              />
              <Source value={latestTroponin} idKey="result_id" />
            </>
          ) : (
            <Empty label="Chưa có kết quả Troponin hiện hành" />
          )}
        </Panel>

        <Panel
          title="Tổng hợp lâm sàng và thẩm quyền bác sĩ"
          link={`/cases/${caseId}/clinical-reasoning`}
          linkLabel="Mở tổng hợp lâm sàng"
        >
          {value.physician_assessment ? (
            <>
              <Fact
                label="Đánh giá"
                value={text(value.physician_assessment.summary)}
              />
              <Fact
                label="Điểm chưa chắc chắn"
                value={text(value.physician_assessment.uncertainty)}
              />
            </>
          ) : (
            <Empty label="Chưa có đánh giá hiệu lực của bác sĩ" />
          )}
          {value.physician_decision ? (
            <div className="vm-authority-block">
              <strong>Quyết định hiện hành chưa bị thu hồi của bác sĩ</strong>
              <p>
                {viDecisionType(text(value.physician_decision.decision_type))}
              </p>
              <p>{text(value.physician_decision.rationale)}</p>
              <Source value={value.physician_decision} idKey="decision_id" />
            </div>
          ) : (
            <Empty label="Chưa có quyết định hiện hành của bác sĩ" />
          )}
          <small>
            Các bản ghi đã sửa, bị thay thế hoặc thu hồi vẫn có trong lịch sử
            Tổng hợp lâm sàng.
          </small>
        </Panel>

        <Panel
          title="Trạng thái quy trình"
          link={`/cases/${caseId}/workflow`}
          linkLabel="Mở quy trình"
        >
          {value.workflow ? (
            <>
              <Fact
                label="Trạng thái hiện tại"
                value={viWorkflowState(text(value.workflow.state))}
              />
              <Fact
                label="Chuyển trạng thái gần nhất"
                value={
                  value.workflow.last_transition_at
                    ? formatTimestamp(text(value.workflow.last_transition_at))
                    : "Chưa ghi nhận chuyển trạng thái"
                }
              />
              <Source value={value.workflow} idKey="workflow_id" />
              <p className="vm-demo-notice">
                {viSafetyNotice(text(value.workflow.demonstration_notice))}
              </p>
            </>
          ) : (
            <Empty label="Chưa có phiên quy trình" />
          )}
        </Panel>

        <Panel
          title="Công việc đang mở và cảnh báo chưa xử lý"
          link={`/cases/${caseId}/workflow`}
          linkLabel="Quản lý trong Quy trình"
        >
          <div className="vm-case-ops-summary">
            <strong>{value.tasks.length}</strong>
            <span>công việc đang mở</span>
            <strong>{value.alerts.length}</strong>
            <span>cảnh báo chưa xử lý</span>
          </div>
          {value.tasks.slice(0, 4).map((task) => (
            <div className="vm-compact-row" key={text(task.task_id)}>
              <span>{viTaskType(text(task.task_type))}</span>
              <strong>{viStatus(text(task.status))}</strong>
              <small>{formatDueLabel(text(task.due_at, ""))}</small>
            </div>
          ))}
          {value.alerts.slice(0, 3).map((alert) => (
            <div
              className="vm-compact-row vm-compact-row--alert"
              key={text(alert.alert_id)}
            >
              <span>{viClinicalTerm(text(alert.message))}</span>
              <strong>{viStatus(text(alert.severity))}</strong>
            </div>
          ))}
          {!value.tasks.length && !value.alerts.length && (
            <Empty label="Không có công việc đang mở hoặc cảnh báo chưa xử lý" />
          )}
        </Panel>

        <Panel
          title="Lịch theo dõi"
          link={`/cases/${caseId}/timeline`}
          linkLabel="Rà soát dòng thời gian / kết cục"
        >
          <div className="vm-scheduling-summary">
            <span>
              <strong>1</strong>
              Khuyến nghị theo dõi của bác sĩ
            </span>
            <span>
              <strong>2</strong>
              Yêu cầu lịch hẹn hành chính
            </span>
            <span>
              <strong>3</strong>
              Nhân viên xác nhận và nhắc lịch
            </span>
            <span>
              <strong>4</strong>
              Đổi lịch, không đến hoặc hoàn tất theo dõi
            </span>
          </div>
          <p className="vm-inline-notice">
            Lịch chỉ được biểu diễn để rà soát quy trình. MVP này chưa có máy
            lịch bệnh viện và không đưa tín hiệu khẩn cấp vào lịch theo dõi
            thường quy.
          </p>
        </Panel>
      </div>

      <section
        className="vm-case-panel vm-case-timeline"
        aria-labelledby="recent-timeline-title"
      >
        <div className="vm-case-panel__heading">
          <h2 id="recent-timeline-title">Dòng thời gian gần đây</h2>
          <Link href={`/cases/${caseId}/timeline`}>
            Xem toàn bộ dòng thời gian
          </Link>
        </div>
        {value.timeline.length ? (
          value.timeline.map((event) => (
            <article key={text(event.timeline_event_id)}>
              <Clock3 size={15} aria-hidden />
              <div>
                <strong>{text(event.title)}</strong>
                <small>
                  {formatTimestamp(text(event.occurred_at))} ·{" "}
                  {text(event.source)}
                </small>
              </div>
            </article>
          ))
        ) : (
          <Empty label="Chưa ghi nhận hoạt động dòng thời gian" />
        )}
        <p className="vm-case-workspace__audit-link">
          Cần xem nguồn gốc?{" "}
          <Link href={`/cases/${caseId}/audit`}>
            Mở nhật ký kiểm chứng đầy đủ
          </Link>
          .
        </p>
      </section>
      <IntegrationStatusPanel />
      <footer className="vm-case-workspace__footer">
        Nguyên mẫu dùng cho nghiên cứu. Không gian này chỉ trình bày bằng chứng
        và điều hướng do backend sở hữu; không tạo thẩm quyền lâm sàng.
      </footer>
    </main>
  );
}

function Panel({
  title,
  link,
  linkLabel,
  ownerLabel,
  children,
}: {
  title: string;
  link?: string;
  linkLabel?: string;
  ownerLabel?: string;
  children: ReactNode;
}) {
  return (
    <section
      className="vm-case-panel"
      aria-labelledby={`${title.replaceAll(" ", "-").toLowerCase()}-title`}
    >
      <div className="vm-case-panel__heading">
        <h2 id={`${title.replaceAll(" ", "-").toLowerCase()}-title`}>
          {title}
        </h2>
        {link && linkLabel ? (
          <Link href={link}>{linkLabel}</Link>
        ) : (
          <span>{ownerLabel}</span>
        )}
      </div>
      {children}
    </section>
  );
}
function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="vm-case-fact">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
function formatMeasurementValue(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return new Intl.NumberFormat("vi-VN", {
      maximumFractionDigits: 2,
    }).format(value);
  }
  if (typeof value === "string" && value.trim().length > 0) {
    return value;
  }
  return "Chưa ghi nhận";
}
function Source({
  value,
  idKey,
}: {
  value: Record<string, unknown>;
  idKey: string;
}) {
  return (
    <small className="vm-source-ref">
      Nguồn {text(value[idKey])} | v{number(value.record_version)}
    </small>
  );
}
function Empty({ label }: { label: string }) {
  return (
    <EmptyState
      title={label}
      description="Chưa rõ là dữ liệu chưa đầy đủ, không phải bằng chứng âm tính."
      compact
    />
  );
}
