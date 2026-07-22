"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Clock3,
  ShieldAlert,
} from "lucide-react";
import { formatDueLabel, formatTimestamp } from "@web/shared/formatting";
import { viClinicalTerm, viStatus, viTaskType } from "@web/shared/locale/vi";
import type { DecisionView } from "@web/features/clinical-reasoning/model";
import type {
  WorkflowAlertView,
  WorkflowOperationsView,
  WorkflowTaskView,
} from "./model";

interface WorkflowStage {
  id: string;
  label: string;
  status: string;
  time?: string | null;
  owner: string;
  source: string;
  quality: string;
  nextAction: string;
  href: string;
}

const stageTemplate = [
  ["patient", "Bệnh nhân và lần tiếp nhận"],
  ["triage", "Tiếp nhận và sinh hiệu"],
  ["ecg-acquisition", "Thu nhận ECG"],
  ["ecg-ai", "Phân tích ECG có AI hỗ trợ"],
  ["physician-ecg", "Bác sĩ diễn giải ECG"],
  ["troponin-t0", "Troponin T0"],
  ["repeat-evidence", "Bằng chứng lặp lại"],
  ["snapshot", "Snapshot bằng chứng lâm sàng"],
  ["assessment", "Đánh giá của bác sĩ"],
  ["decision", "Quyết định của bác sĩ"],
  ["workflow", "Quy trình và công việc"],
  ["scheduling", "Lịch theo dõi"],
  ["outcome", "Kết cục và kiểm chứng"],
] as const;

export function ClinicalWorkflowBoard({
  caseId,
  value,
  decisions,
  activeTasks,
  alerts,
}: {
  caseId: string;
  value: WorkflowOperationsView;
  decisions: DecisionView[];
  activeTasks: WorkflowTaskView[];
  alerts: WorkflowAlertView[];
}) {
  const effectiveDecision = decisions.find((decision) => decision.effective);
  const stages = buildStages(
    caseId,
    value,
    activeTasks,
    alerts,
    effectiveDecision,
  );
  const selectedStage =
    stages.find((stage) => stage.status === "overdue") ??
    stages.find((stage) => stage.status === "in progress") ??
    stages.find((stage) => stage.status === "under review") ??
    stages.find((stage) => stage.status === "pending") ??
    stages[0] ??
    fallbackStage(caseId);

  return (
    <section
      className="vm-clinical-board"
      aria-labelledby="clinical-workflow-board-title"
    >
      <div className="vm-clinical-board__intro">
        <div>
          <p className="vm-eyebrow">Bảng quy trình lâm sàng</p>
          <h3 id="clinical-workflow-board-title">
            Bằng chứng và điều phối theo chỉ đạo bác sĩ
          </h3>
          <p>
            Đây chỉ là bảng điều phối. Nó hiển thị bằng chứng đã lưu, thẩm quyền
            bác sĩ và công việc quy trình; không tự chọn hướng chẩn đoán.
          </p>
        </div>
        <span className="vm-status-pill vm-status-pill--technically-limited">
          Quy trình minh họa
        </span>
      </div>

      <div className="vm-clinical-board__layout">
        <ol className="vm-workflow-rail" aria-label="Các bước quy trình ACS">
          {stages.map((stage) => (
            <li key={stage.id}>
              <Link
                href={stage.href}
                className={`vm-stage-card is-${stage.status.replaceAll(" ", "-")}`}
              >
                <span className="vm-stage-card__marker" aria-hidden="true" />
                <strong>{stage.label}</strong>
                <span>{viStatus(stage.status)}</span>
                {stage.time ? (
                  <small>{formatTimestamp(stage.time)}</small>
                ) : null}
              </Link>
            </li>
          ))}
        </ol>

        <div className="vm-branch-board" aria-label="Nhánh quy trình hiện tại">
          <BranchCard
            title="Công việc đang mở theo chỉ đạo bác sĩ"
            icon={<Clock3 size={17} aria-hidden />}
            status={activeTasks.length ? "in progress" : "not started"}
            detail={`${activeTasks.length} công việc đang mở.`}
            href={`/cases/${caseId}/workflow`}
          >
            {activeTasks.length ? (
              activeTasks
                .slice(0, 4)
                .map((task) => (
                  <BranchItem
                    key={task.task_id}
                    title={viTaskType(task.task_type)}
                    status={task.status}
                    detail={formatDueLabel(task.due_at)}
                    source={task.source_type}
                  />
                ))
            ) : (
              <p>Chưa tạo công việc điều phối đang mở.</p>
            )}
          </BranchCard>

          <BranchCard
            title="Cảnh báo cần rà soát"
            icon={<AlertTriangle size={17} aria-hidden />}
            status={alerts.length ? "under review" : "available"}
            detail={`${alerts.length} cảnh báo chưa xử lý.`}
            href={`/cases/${caseId}/workflow`}
          >
            {alerts.length ? (
              alerts
                .slice(0, 3)
                .map((alert) => (
                  <BranchItem
                    key={alert.alert_id}
                    title={viClinicalTerm(alert.alert_type)}
                    status={alert.status}
                    detail={alert.message}
                    source={alert.source}
                  />
                ))
            ) : (
              <p>Hiện chưa ghi nhận cảnh báo quy trình chưa xử lý.</p>
            )}
          </BranchCard>

          <BranchCard
            title="Luồng rà soát ngay"
            icon={<ShieldAlert size={17} aria-hidden />}
            status={immediateReviewStatus(effectiveDecision, alerts)}
            detail="Hành động hướng khẩn cấp chỉ được hiển thị khi thẩm quyền bác sĩ, công việc hoặc cảnh báo đã được lưu."
            href={`/cases/${caseId}/workflow`}
          >
            {effectiveDecision?.decision_type === "request_cath_lab_review" ? (
              <BranchItem
                title="Bác sĩ yêu cầu xem xét can thiệp"
                status={effectiveDecision.status}
                detail={effectiveDecision.rationale}
                source="quyết định bác sĩ"
              />
            ) : alerts.some((alert) => alert.severity === "critical") ? (
              alerts
                .filter((alert) => alert.severity === "critical")
                .slice(0, 2)
                .map((alert) => (
                  <BranchItem
                    key={alert.alert_id}
                    title={viClinicalTerm(alert.alert_type)}
                    status={alert.status}
                    detail={alert.message}
                    source={alert.source}
                  />
                ))
            ) : (
              <p>
                Chưa có thẩm quyền rà soát ngay được lưu. UI không suy luận
                chuyển tuyến, kích hoạt can thiệp hoặc điều phối cấp cứu.
              </p>
            )}
          </BranchCard>

          <BranchCard
            title="Bằng chứng lặp lại đã lên hạn"
            icon={<CalendarClock size={17} aria-hidden />}
            status={schedulingStatus(effectiveDecision, activeTasks)}
            detail="ECG lặp lại, Troponin lặp lại và công việc theo dõi chỉ xuất hiện từ công việc/nhắc việc backend đã lưu."
            href={`/cases/${caseId}/timeline`}
          >
            <ol className="vm-schedule-flow">
              <li>Yêu cầu do bác sĩ ghi nhận</li>
              <li>Công việc quy trình backend hoặc nhắc ECG</li>
              <li>Hạn xử lý và phân công phụ trách</li>
              <li>Hoàn tất, hủy hoặc leo thang quá hạn</li>
            </ol>
            <small>
              MVP này chưa triển khai lịch hẹn bệnh viện. Tín hiệu cần rà soát
              ngay được tách khỏi lịch thường quy.
            </small>
          </BranchCard>
        </div>

        <aside
          className="vm-board-detail"
          aria-label="Chi tiết bước quy trình đang chọn"
        >
          <h3>{selectedStage.label}</h3>
          <dl>
            <dt>Trạng thái</dt>
            <dd>{viStatus(selectedStage.status)}</dd>
            <dt>Phụ trách</dt>
            <dd>{selectedStage.owner}</dd>
            <dt>Nguồn bằng chứng</dt>
            <dd>{selectedStage.source}</dd>
            <dt>Chất lượng hoặc giới hạn</dt>
            <dd>{selectedStage.quality}</dd>
            <dt>Hành động tiếp theo</dt>
            <dd>{selectedStage.nextAction}</dd>
          </dl>
          <Link className="vm-button" href={selectedStage.href}>
            Mở không gian nguồn
          </Link>
        </aside>
      </div>
    </section>
  );
}

function buildStages(
  caseId: string,
  value: WorkflowOperationsView,
  activeTasks: WorkflowTaskView[],
  alerts: WorkflowAlertView[],
  decision?: DecisionView,
): WorkflowStage[] {
  const taskByType = new Map(activeTasks.map((task) => [task.task_type, task]));
  const hasRepeatTask =
    taskByType.has("repeat_ecg") || taskByType.has("repeat_troponin");
  const hasOverdue = activeTasks.some((task) => task.status === "overdue");
  return stageTemplate.map(([id, label]) => {
    const href = hrefForStage(caseId, id);
    const base = {
      id,
      label,
      owner: ownerForStage(id),
      source: sourceForStage(id),
      quality: "Bảng này chưa ghi nhận giới hạn kỹ thuật.",
      nextAction: "Rà soát không gian nguồn.",
      href,
    };
    if (id === "workflow") {
      return {
        ...base,
        status: hasOverdue
          ? "overdue"
          : activeTasks.length
            ? "in progress"
            : "available",
        time: activeTasks[0]?.due_at ?? null,
        quality: alerts.length
          ? `${alerts.length} cảnh báo chưa xử lý`
          : "Không có cảnh báo quy trình chưa xử lý.",
        nextAction: activeTasks.length
          ? "Xử lý các công việc đang mở theo chỉ đạo bác sĩ."
          : "Chờ công việc điều phối do bác sĩ chỉ đạo.",
      };
    }
    if (id === "decision") {
      return {
        ...base,
        status: decision ? "available" : "pending",
        time: decision?.recorded_at ?? null,
        quality: decision
          ? "Quyết định hiện hành chưa bị thu hồi do bác sĩ ghi nhận."
          : "Chưa có quyết định hiệu lực của bác sĩ.",
        nextAction: decision
          ? "Chỉ tạo công việc điều phối khi phù hợp."
          : "Ghi nhận quyết định bác sĩ trong Tổng hợp lâm sàng.",
      };
    }
    if (id === "repeat-evidence") {
      return {
        ...base,
        status: hasRepeatTask ? "in progress" : "not started",
        time:
          taskByType.get("repeat_ecg")?.due_at ??
          taskByType.get("repeat_troponin")?.due_at ??
          null,
        quality: hasRepeatTask
          ? "Bằng chứng lặp lại được yêu cầu bởi công việc quy trình đã lưu."
          : "Hiện không có công việc bằng chứng lặp lại đang mở.",
        nextAction: hasRepeatTask
          ? "Hoàn tất bằng chứng lặp lại trong không gian ECG hoặc Troponin phụ trách."
          : "Không thao tác nếu bác sĩ chưa yêu cầu bằng chứng lặp lại.",
      };
    }
    if (id === "scheduling") {
      return {
        ...base,
        status: schedulingStatus(decision, activeTasks),
        quality:
          "Lịch được biểu diễn nhưng chưa tự động hóa trong MVP hiện tại.",
        nextAction:
          "Dùng ghi nhận kết cục/dòng thời gian cho đến khi có module lịch.",
      };
    }
    return {
      ...base,
      status: inferredStageStatus(id, value, decision),
      nextAction: nextActionForStage(id),
    };
  });
}

function fallbackStage(caseId: string): WorkflowStage {
  return {
    id: "workflow",
    label: "Quy trình và công việc",
    status: "pending",
    owner: "Đội lâm sàng",
    source: "Vận hành quy trình",
    quality: "Projection quy trình không khả dụng.",
    nextAction: "Làm mới không gian Quy trình.",
    href: `/cases/${caseId}/workflow`,
  };
}

function inferredStageStatus(
  id: string,
  value: WorkflowOperationsView,
  decision?: DecisionView,
) {
  if (id === "assessment") return decision ? "available" : "pending";
  if (id === "snapshot") return decision ? "available" : "pending";
  if (id === "outcome")
    return value.workflow.state === "closed" ? "completed" : "pending";
  if (
    [
      "patient",
      "triage",
      "ecg-acquisition",
      "ecg-ai",
      "physician-ecg",
      "troponin-t0",
    ].includes(id)
  ) {
    return "available";
  }
  return "pending";
}

function schedulingStatus(
  decision: DecisionView | undefined,
  activeTasks: WorkflowTaskView[],
) {
  if (
    activeTasks.some((task) =>
      ["repeat_ecg", "repeat_troponin", "cardiology_review"].includes(
        task.task_type,
      ),
    )
  ) {
    return "in progress";
  }
  return decision?.decision_type === "other_documented_plan"
    ? "pending"
    : "not started";
}

function immediateReviewStatus(
  decision: DecisionView | undefined,
  alerts: WorkflowAlertView[],
) {
  if (decision?.decision_type === "request_cath_lab_review")
    return "under review";
  if (alerts.some((alert) => alert.severity === "critical")) return "overdue";
  return "not started";
}

function hrefForStage(caseId: string, id: string) {
  if (id === "triage") return `/cases/${caseId}/documentation`;
  if (id.startsWith("ecg") || id === "physician-ecg")
    return `/cases/${caseId}/ecg`;
  if (id === "troponin-t0" || id === "repeat-evidence")
    return `/cases/${caseId}/troponin`;
  if (["snapshot", "assessment", "decision"].includes(id))
    return `/cases/${caseId}/clinical-reasoning`;
  if (id === "workflow") return `/cases/${caseId}/workflow`;
  if (id === "outcome" || id === "scheduling")
    return `/cases/${caseId}/timeline`;
  return `/cases/${caseId}`;
}

function ownerForStage(id: string) {
  if (id.includes("physician") || ["assessment", "decision"].includes(id)) {
    return "Bác sĩ";
  }
  if (id === "scheduling")
    return "Nhân viên hành chính sau khuyến nghị của bác sĩ";
  if (id === "workflow") return "Người hoặc nhóm điều phối được phân công";
  return "Đội lâm sàng";
}

function sourceForStage(id: string) {
  if (id.includes("ecg")) return "Không gian ECG";
  if (id.includes("troponin")) return "Không gian Troponin";
  if (id === "scheduling") return "Biểu diễn kết cục/dòng thời gian";
  if (id === "workflow") return "Vận hành quy trình";
  return "Không gian ca";
}

function nextActionForStage(id: string) {
  if (id === "triage") return "Rà soát hoặc chỉnh sửa ghi nhận.";
  if (id === "ecg-ai")
    return "Chạy hoặc rà soát suy luận mô hình kèm nguồn gốc.";
  if (id === "physician-ecg") return "Ghi nhận diễn giải ECG của bác sĩ.";
  if (id === "troponin-t0")
    return "Rà soát kết quả nối tiếp và delta do backend phụ trách.";
  if (id === "assessment") return "Ghi nhận đánh giá của bác sĩ.";
  return "Rà soát không gian nguồn.";
}

function BranchCard({
  title,
  status,
  detail,
  icon,
  href,
  children,
}: {
  title: string;
  status: string;
  detail: string;
  icon: ReactNode;
  href: string;
  children: ReactNode;
}) {
  return (
    <article className="vm-branch-card">
      <header>
        <span aria-hidden="true">{icon}</span>
        <div>
          <h4>{title}</h4>
          <p>{detail}</p>
        </div>
        <span
          className={`vm-status-pill vm-status-pill--${status.replaceAll(" ", "-")}`}
        >
          {status}
        </span>
      </header>
      <div>{children}</div>
      <Link href={href}>Mở không gian nguồn</Link>
    </article>
  );
}

function BranchItem({
  title,
  status,
  detail,
  source,
}: {
  title: string;
  status: string;
  detail: string;
  source: string;
}) {
  return (
    <div className="vm-branch-item">
      <CheckCircle2 size={15} aria-hidden />
      <div>
        <strong>{title}</strong>
        <p>{detail}</p>
        <small>
          {viStatus(status)} - {viClinicalTerm(source)}
        </small>
      </div>
    </div>
  );
}

function taskLabel(code: string) {
  const labels: Record<string, string> = {
    repeat_ecg: "Lặp lại ECG",
    repeat_troponin: "Lặp lại Troponin",
    obtain_additional_information: "Bổ sung thông tin",
    cardiology_review: "Hội chẩn Tim mạch",
    cath_lab_review: "Bác sĩ yêu cầu xem xét can thiệp",
    physician_reassessment: "Bác sĩ đánh giá lại",
  };
  return labels[code] ?? viTaskType(code);
}

function formatCode(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
