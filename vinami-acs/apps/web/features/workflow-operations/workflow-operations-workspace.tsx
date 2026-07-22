"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import {
  AlertTriangle,
  BellRing,
  Clock3,
  History,
  ListChecks,
  UserRoundCheck,
} from "lucide-react";
import { createBrowserApiClient } from "@web/shared/api/browser";
import { formatDueTimestamp, formatTimestamp } from "@web/shared/formatting";
import {
  viAction,
  viDecisionType,
  viPriority,
  viSafetyNotice,
  viStatus,
  viTaskType,
  viWorkflowState,
} from "@web/shared/locale/vi";
import type { DecisionView } from "@web/features/clinical-reasoning/model";
import { AlertDigestPanel } from "@web/features/evidence/evidence-automation-panel";
import {
  workflowOperationsSchema,
  type WorkflowAlertView,
  type WorkflowOperationsView,
  type WorkflowTaskView,
} from "./model";
import { ClinicalWorkflowBoard } from "./clinical-workflow-board";

const taskLabels: Record<string, string> = {
  repeat_ecg: "Lặp lại ECG",
  repeat_troponin: "Lặp lại Troponin",
  obtain_additional_information: "Bổ sung thông tin",
  cardiology_review: "Hội chẩn Tim mạch",
  cath_lab_review: "Bác sĩ yêu cầu xem xét can thiệp",
  physician_reassessment: "Bác sĩ đánh giá lại",
  other_documented_task: "Công việc khác đã ghi nhận",
};

const actionableDecisions = new Set([
  "request_repeat_ecg",
  "request_repeat_troponin",
  "request_additional_information",
  "request_cardiology_review",
  "request_cath_lab_review",
  "other_documented_plan",
]);

type TaskAction = "assign" | "acknowledge" | "start" | "complete" | "cancel";
type AlertAction = "acknowledge" | "resolve";
type GenerateForm = {
  priority: "routine" | "priority" | "urgent";
  dueAt: string;
};
type ReasonForm = { reason: string };

export function WorkflowOperationsWorkspace({
  caseId,
  actorId,
  initialValue,
  decisions,
}: {
  caseId: string;
  actorId: string;
  initialValue: WorkflowOperationsView;
  decisions: DecisionView[];
}) {
  const api = useMemo(() => createBrowserApiClient(), []);
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["workflow-operations", caseId],
    initialData: initialValue,
    queryFn: async () =>
      workflowOperationsSchema.parse(
        await api.getWorkflowOperationsWorkspace(caseId),
      ),
  });
  const value = query.data;
  const [selectedDecision, setSelectedDecision] = useState<DecisionView | null>(
    null,
  );
  const [taskAction, setTaskAction] = useState<{
    task: WorkflowTaskView;
    action: TaskAction;
  } | null>(null);
  const [alertAction, setAlertAction] = useState<{
    alert: WorkflowAlertView;
    action: AlertAction;
  } | null>(null);
  const generateForm = useForm<GenerateForm>({
    defaultValues: { priority: "routine", dueAt: "" },
  });
  const reasonForm = useForm<ReasonForm>({ defaultValues: { reason: "" } });
  const refresh = () =>
    queryClient.invalidateQueries({
      queryKey: ["workflow-operations", caseId],
    });

  const generateMutation = useMutation({
    mutationFn: async (form: GenerateForm) => {
      if (!selectedDecision) throw new Error("Chọn một quyết định của bác sĩ.");
      return api.generateWorkflowTask(
        caseId,
        {
          decision_id: selectedDecision.decision_id,
          expected_decision_version: selectedDecision.record_version,
          expected_workflow_version: value.workflow.version,
          priority: form.priority,
          due_at: form.dueAt ? new Date(form.dueAt).toISOString() : null,
        },
        crypto.randomUUID(),
      );
    },
    onSuccess: async () => {
      setSelectedDecision(null);
      generateForm.reset();
      await refresh();
    },
  });
  const taskMutation = useMutation({
    mutationFn: async (form: ReasonForm) => {
      if (!taskAction) throw new Error("Chọn một hành động công việc.");
      return api.changeWorkflowTask(
        caseId,
        taskAction.task.task_id,
        taskAction.action,
        {
          expected_version: taskAction.task.version,
          owner_user_id: taskAction.action === "assign" ? actorId : null,
          owner_team_id: null,
          reason:
            taskAction.action === "complete" || taskAction.action === "cancel"
              ? form.reason
              : null,
        },
        crypto.randomUUID(),
      );
    },
    onSuccess: async () => {
      setTaskAction(null);
      reasonForm.reset();
      await refresh();
    },
  });
  const alertMutation = useMutation({
    mutationFn: async (form: ReasonForm) => {
      if (!alertAction) throw new Error("Chọn một hành động cảnh báo.");
      return api.changeWorkflowAlert(
        caseId,
        alertAction.alert.alert_id,
        alertAction.action,
        {
          expected_version: alertAction.alert.version,
          reason: alertAction.action === "resolve" ? form.reason : null,
        },
        crypto.randomUUID(),
      );
    },
    onSuccess: async () => {
      setAlertAction(null);
      reasonForm.reset();
      await refresh();
    },
  });
  const overdueMutation = useMutation({
    mutationFn: () => api.evaluateWorkflowOverdue(caseId, crypto.randomUUID()),
    onSuccess: refresh,
  });

  const activeTasks = value.tasks.filter(
    (task) => !["completed", "cancelled"].includes(task.status),
  );
  const historicalTasks = value.tasks.filter((task) =>
    ["completed", "cancelled"].includes(task.status),
  );
  const availableDecisions = decisions.filter(
    (decision) =>
      decision.effective &&
      actionableDecisions.has(decision.decision_type) &&
      !value.tasks.some(
        (task) => task.originating_decision_id === decision.decision_id,
      ),
  );

  return (
    <main className="vm-workflow-workspace">
      <section className="vm-card vm-workflow-hero">
        <div className="vm-card__body">
          <div>
            <p className="vm-eyebrow">Quy trình điều phối</p>
            <h2>{viWorkflowState(value.workflow.state)}</h2>
            <p>
              Quy trình v{value.workflow.version} | Định nghĩa{" "}
              {value.workflow.definition_version}
            </p>
          </div>
          <button
            className="vm-button"
            disabled={overdueMutation.isPending}
            onClick={() => overdueMutation.mutate()}
          >
            <Clock3 size={16} /> Đánh giá hạn xử lý
          </button>
        </div>
        <p className="vm-safety-note">{viSafetyNotice(value.safety_notice)}</p>
        <p className="vm-demo-notice">
          {viSafetyNotice(value.workflow.demonstration_notice)}
        </p>
      </section>

      <div className="vm-workflow-summary" aria-label="Tóm tắt quy trình">
        <Metric label="Công việc đang mở" value={activeTasks.length} />
        <Metric
          label="Quá hạn / leo thang"
          value={activeTasks.filter((task) => task.status === "overdue").length}
        />
        <Metric
          label="Cảnh báo chưa xử lý"
          value={
            value.alerts.filter((alert) => alert.status !== "resolved").length
          }
        />
        <Metric label="Hoàn tất / đã hủy" value={historicalTasks.length} />
      </div>

      <ClinicalWorkflowBoard
        caseId={caseId}
        value={value}
        decisions={decisions}
        activeTasks={activeTasks}
        alerts={value.alerts.filter((alert) => alert.status !== "resolved")}
      />

      <section className="vm-card">
        <div className="vm-card__body">
          <div className="vm-section-heading">
            <div>
              <h3>
                Yêu cầu do bác sĩ ghi nhận đang chờ chuyển thành công việc
              </h3>
              <p>Công việc chỉ được tạo từ quyết định hiệu lực đã lưu.</p>
            </div>
          </div>
          {!availableDecisions.length && (
            <p>Hiện không có yêu cầu bác sĩ nào chưa xử lý.</p>
          )}
          {availableDecisions.map((decision) => (
            <article className="vm-workflow-row" key={decision.decision_id}>
              <div>
                <strong>{decisionLabel(decision.decision_type)}</strong>
                <p>{decision.rationale}</p>
                <small>Ghi nhận {formatTimestamp(decision.recorded_at)}</small>
              </div>
              <button
                className="vm-button vm-button--primary"
                onClick={() => setSelectedDecision(decision)}
              >
                Tạo công việc điều phối
              </button>
            </article>
          ))}
        </div>
      </section>

      <section className="vm-card" aria-labelledby="active-task-heading">
        <div className="vm-card__body">
          <h3 id="active-task-heading">
            <ListChecks size={18} /> Công việc đang mở
          </h3>
          {!activeTasks.length && <p>Không có công việc điều phối đang mở.</p>}
          <div className="vm-workflow-list">
            {activeTasks.map((task) => (
              <TaskCard
                key={task.task_id}
                task={task}
                onAction={(action) => {
                  reasonForm.reset();
                  setTaskAction({ task, action });
                }}
              />
            ))}
          </div>
        </div>
      </section>

      <section className="vm-card" aria-labelledby="alert-heading">
        <div className="vm-card__body">
          <h3 id="alert-heading">
            <BellRing size={18} /> Cảnh báo cần con người rà soát
          </h3>
          <p>
            Được nhóm theo chính sách backend; cảnh báo thô vẫn hiển thị bên
            dưới.
          </p>
          <AlertDigestPanel digest={value.alert_digest} />
          {!value.alerts.length && <p>Chưa ghi nhận cảnh báo điều phối.</p>}
          {value.alerts.map((alert) => (
            <article
              className={`vm-alert-row vm-alert-row--${alert.severity}`}
              key={alert.alert_id}
            >
              <div>
                <strong>{formatCode(alert.alert_type)}</strong>
                <p>{alert.message}</p>
                <small>
                  {viStatus(alert.status)} | v{alert.version} |{" "}
                  {formatTimestamp(alert.raised_at)}
                </small>
              </div>
              <div className="vm-inline-actions">
                {alert.status === "active" && (
                  <button
                    className="vm-button"
                    onClick={() =>
                      setAlertAction({ alert, action: "acknowledge" })
                    }
                  >
                    Ghi nhận
                  </button>
                )}
                {alert.status === "acknowledged" && (
                  <button
                    className="vm-button"
                    onClick={() => setAlertAction({ alert, action: "resolve" })}
                  >
                    Xử lý xong
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="vm-card">
        <div className="vm-card__body">
          <h3>
            <History size={18} /> Lịch sử hoàn tất và đã hủy
          </h3>
          {!historicalTasks.length && (
            <p>Chưa có công việc hoàn tất hoặc đã hủy.</p>
          )}
          {historicalTasks.map((task) => (
            <article className="vm-workflow-row" key={task.task_id}>
              <div>
                <strong>{taskLabel(task.task_type)}</strong>
                <p>{task.outcome ?? task.cancellation_reason}</p>
              </div>
              <span className={`vm-status-pill vm-status-pill--${task.status}`}>
                {task.status}
              </span>
            </article>
          ))}
        </div>
      </section>

      <nav
        className="vm-card vm-reasoning-links"
        aria-label="Related workflow records"
      >
        <Link href={`/cases/${caseId}/clinical-reasoning`}>
          Tổng hợp lâm sàng
        </Link>
        <Link href={`/cases/${caseId}/timeline`}>Dòng thời gian</Link>
        <Link href={`/cases/${caseId}/audit`}>Nhật ký kiểm chứng</Link>
      </nav>

      {selectedDecision && (
        <Dialog
          title="Tạo công việc điều phối"
          onCancel={() => setSelectedDecision(null)}
        >
          <form
            className="vm-form-stack"
            onSubmit={generateForm.handleSubmit((form) =>
              generateMutation.mutate(form),
            )}
          >
            <p>
              <strong>{decisionLabel(selectedDecision.decision_type)}</strong>
            </p>
            <label>
              Ưu tiên
              <select {...generateForm.register("priority")}>
                <option value="routine">Thường quy</option>
                <option value="priority">Ưu tiên</option>
                <option value="urgent">Ưu tiên cao</option>
              </select>
            </label>
            <label>
              Hạn xử lý (tùy chọn)
              <input
                type="datetime-local"
                {...generateForm.register("dueAt")}
              />
            </label>
            <p>
              Công việc này chỉ ghi nhận hoạt động điều phối. Không tạo chẩn
              đoán, chỉ định điều trị hoặc đóng ca.
            </p>
            <button
              className="vm-button vm-button--primary"
              disabled={generateMutation.isPending}
            >
              Xác nhận tạo công việc
            </button>
            <MutationError error={generateMutation.error} />
          </form>
        </Dialog>
      )}

      {taskAction && (
        <Dialog
          title={`${viAction(taskAction.action)} công việc`}
          onCancel={() => setTaskAction(null)}
        >
          <form
            className="vm-form-stack"
            onSubmit={reasonForm.handleSubmit((form) =>
              taskMutation.mutate(form),
            )}
          >
            <p>
              <strong>{taskLabel(taskAction.task.task_type)}</strong>
            </p>
            {taskAction.action === "assign" && (
              <p>
                <UserRoundCheck size={16} /> Gán công việc này cho danh tính đã
                xác thực của bạn.
              </p>
            )}
            {["complete", "cancel"].includes(taskAction.action) && (
              <label>
                Lý do bắt buộc
                <textarea
                  {...reasonForm.register("reason", { required: true })}
                />
              </label>
            )}
            <button
              className="vm-button vm-button--primary"
              disabled={taskMutation.isPending}
            >
              Xác nhận {viAction(taskAction.action)}
            </button>
            <MutationError error={taskMutation.error} />
          </form>
        </Dialog>
      )}

      {alertAction && (
        <Dialog
          title={`${viAction(alertAction.action)} cảnh báo`}
          onCancel={() => setAlertAction(null)}
        >
          <form
            className="vm-form-stack"
            onSubmit={reasonForm.handleSubmit((form) =>
              alertMutation.mutate(form),
            )}
          >
            <p>{alertAction.alert.message}</p>
            {alertAction.action === "resolve" && (
              <label>
                Lý do xử lý
                <textarea
                  {...reasonForm.register("reason", { required: true })}
                />
              </label>
            )}
            <p>
              Ghi nhận và xử lý cảnh báo không thay thế thẩm quyền lâm sàng.
            </p>
            <button
              className="vm-button vm-button--primary"
              disabled={alertMutation.isPending}
            >
              Xác nhận {viAction(alertAction.action)}
            </button>
            <MutationError error={alertMutation.error} />
          </form>
        </Dialog>
      )}
    </main>
  );
}

function TaskCard({
  task,
  onAction,
}: {
  task: WorkflowTaskView;
  onAction: (action: TaskAction) => void;
}) {
  const actions: Record<string, TaskAction[]> = {
    pending: ["assign", "cancel"],
    assigned: ["acknowledge", "cancel"],
    acknowledged: ["start", "cancel"],
    overdue: ["start", "cancel"],
    in_progress: ["complete", "cancel"],
  };
  return (
    <article className={`vm-task-card vm-task-card--${task.status}`}>
      <div className="vm-task-card__header">
        <div>
          <span
            className={`vm-priority-pill vm-priority-pill--${task.priority}`}
          >
            {viPriority(task.priority)}
          </span>
          <h4>{taskLabel(task.task_type)}</h4>
        </div>
        <span className={`vm-status-pill vm-status-pill--${task.status}`}>
          {viStatus(task.status)}
        </span>
      </div>
      <dl>
        <dt>Hạn xử lý</dt>
        <dd>{formatDueTimestamp(task.due_at)}</dd>
        <dt>Phụ trách</dt>
        <dd>
          {task.owner_user_id
            ? "Người dùng đã được gán"
            : task.owner_team_id
              ? "Nhóm đã được gán"
              : "Chưa phân công"}
        </dd>
        <dt>Leo thang</dt>
        <dd>{task.escalation_level}</dd>
        <dt>Nguồn</dt>
        <dd>
          {task.originating_decision?.rationale ?? "Hiệu ứng quy trình đã lưu"}
        </dd>
      </dl>
      <div className="vm-inline-actions">
        {(actions[task.status] ?? []).map((action) => (
          <button
            className="vm-button"
            key={action}
            onClick={() => onAction(action)}
          >
            {viAction(action)}
          </button>
        ))}
      </div>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
function Dialog({
  title,
  onCancel,
  children,
}: {
  title: string;
  onCancel: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="vm-dialog-backdrop" role="presentation">
      <div
        className="vm-confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="workflow-dialog-title"
      >
        <div className="vm-section-heading">
          <h3 id="workflow-dialog-title">{title}</h3>
          <button className="vm-button" onClick={onCancel}>
            Đóng
          </button>
        </div>
        {children}
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
function taskLabel(code: string) {
  return taskLabels[code] ?? viTaskType(code);
}
function decisionLabel(code: string) {
  return code === "request_cath_lab_review"
    ? "Bác sĩ yêu cầu xem xét can thiệp"
    : viDecisionType(code);
}
function formatCode(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
