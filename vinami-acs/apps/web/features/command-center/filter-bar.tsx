"use client";

import type { CommandCenterQuery } from "@vinami/api-client";
import { viWorkflowState } from "@web/shared/locale/vi";

export interface CommandFilters {
  priority: "" | "routine" | "urgent" | "critical";
  workflowState: "" | NonNullable<CommandCenterQuery["workflow_state"]>;
  overdue: "" | "true" | "false";
  alertStatus: "" | "active" | "acknowledged" | "unresolved" | "none";
  evidenceStatus: "" | "current" | "missing" | "stale" | "technical_limit";
  owner: string;
  sort: "priority" | "opened_at" | "next_due_at" | "latest_activity";
  direction: "asc" | "desc";
}

const workflowStates = [
  "NEW",
  "TRIAGE_IN_PROGRESS",
  "AWAITING_ECG",
  "ECG_UNDER_REVIEW",
  "AWAITING_TROPONIN",
  "OBSERVATION",
  "PHYSICIAN_REVIEW_REQUIRED",
  "PATHWAY_SELECTED",
  "TRANSFER_IN_PROGRESS",
  "CATH_LAB_REVIEW",
  "DISCHARGE_REVIEW",
];

export function FilterBar({
  value,
  onChange,
}: {
  value: CommandFilters;
  onChange: (next: CommandFilters) => void;
}) {
  const set = <Key extends keyof CommandFilters>(
    field: Key,
    fieldValue: CommandFilters[Key],
  ) => onChange({ ...value, [field]: fieldValue });
  const owner = value.owner.trim();
  const invalidOwner = Boolean(owner) && !isUuid(owner);
  const activeFilterCount = [
    value.priority,
    value.workflowState,
    value.overdue,
    value.alertStatus,
    value.evidenceStatus,
    owner,
  ].filter(Boolean).length;
  return (
    <section
      className="vm-command-filter-card"
      aria-label="Bộ lọc Trung tâm điều phối"
    >
      <div className="vm-command-filter-card__heading">
        <div>
          <h2>Bộ lọc hàng đợi</h2>
          <p>
            Ưu tiên, hạn xử lý, cảnh báo và trạng thái bằng chứng đều đến từ
            backend.
          </p>
        </div>
        <span className="vm-filter-count">
          {activeFilterCount
            ? `${activeFilterCount} bộ lọc đang bật`
            : "Chưa lọc"}
        </span>
      </div>

      <div className="vm-command-filters">
        <label className="vm-field">
          <span>Ưu tiên</span>
          <select
            value={value.priority}
            onChange={(event) =>
              set("priority", event.target.value as CommandFilters["priority"])
            }
          >
            <option value="">Tất cả mức ưu tiên</option>
            <option value="critical">Khẩn cấp</option>
            <option value="urgent">Ưu tiên cao</option>
            <option value="routine">Thường quy</option>
          </select>
        </label>
        <label className="vm-field">
          <span>Quy trình</span>
          <select
            value={value.workflowState}
            onChange={(event) =>
              set(
                "workflowState",
                event.target.value as CommandFilters["workflowState"],
              )
            }
          >
            <option value="">Tất cả trạng thái quy trình</option>
            {workflowStates.map((state) => (
              <option key={state} value={state}>
                {viWorkflowState(state)}
              </option>
            ))}
          </select>
        </label>
        <label className="vm-field">
          <span>Hạn xử lý</span>
          <select
            value={value.overdue}
            onChange={(event) =>
              set("overdue", event.target.value as CommandFilters["overdue"])
            }
          >
            <option value="">Tất cả trạng thái hạn</option>
            <option value="true">Quá hạn</option>
            <option value="false">Chưa quá hạn</option>
          </select>
        </label>
        <label className="vm-field">
          <span>Cảnh báo</span>
          <select
            value={value.alertStatus}
            onChange={(event) =>
              set(
                "alertStatus",
                event.target.value as CommandFilters["alertStatus"],
              )
            }
          >
            <option value="">Tất cả trạng thái cảnh báo</option>
            <option value="unresolved">Có cảnh báo chưa xử lý</option>
            <option value="active">Đang hoạt động</option>
            <option value="acknowledged">Đã ghi nhận</option>
            <option value="none">Không có cảnh báo chưa xử lý</option>
          </select>
        </label>
        <label className="vm-field">
          <span>Bằng chứng</span>
          <select
            value={value.evidenceStatus}
            onChange={(event) =>
              set(
                "evidenceStatus",
                event.target.value as CommandFilters["evidenceStatus"],
              )
            }
          >
            <option value="">Tất cả trạng thái bằng chứng</option>
            <option value="current">Hiện hành</option>
            <option value="missing">Thiếu dữ liệu</option>
            <option value="stale">Đã cũ</option>
            <option value="technical_limit">Giới hạn kỹ thuật</option>
          </select>
        </label>
        <label className="vm-field vm-field--owner">
          <span>UUID người/nhóm phụ trách</span>
          <input
            value={value.owner}
            placeholder="UUID tùy chọn"
            aria-invalid={invalidOwner}
            aria-describedby="command-owner-filter-help"
            onChange={(event) => set("owner", event.target.value)}
          />
          <small id="command-owner-filter-help">
            {invalidOwner
              ? "Nhập UUID hợp lệ để áp dụng bộ lọc."
              : "Mã định danh chính xác của người hoặc nhóm trên backend."}
          </small>
        </label>
        <label className="vm-field">
          <span>Sắp xếp theo</span>
          <select
            value={value.sort}
            onChange={(event) =>
              set("sort", event.target.value as CommandFilters["sort"])
            }
          >
            <option value="priority">Ưu tiên điều phối</option>
            <option value="next_due_at">Hạn xử lý tiếp theo</option>
            <option value="latest_activity">Hoạt động gần nhất</option>
            <option value="opened_at">Thời điểm mở ca</option>
          </select>
        </label>
        <label className="vm-field">
          <span>Thứ tự</span>
          <select
            value={value.direction}
            onChange={(event) =>
              set(
                "direction",
                event.target.value as CommandFilters["direction"],
              )
            }
          >
            <option value="desc">Giảm dần</option>
            <option value="asc">Tăng dần</option>
          </select>
        </label>
        <div className="vm-filter-actions">
          <button
            className="vm-button"
            type="button"
            onClick={() =>
              onChange({
                priority: "",
                workflowState: "",
                overdue: "",
                alertStatus: "",
                evidenceStatus: "",
                owner: "",
                sort: "priority",
                direction: "desc",
              })
            }
          >
            Xóa lọc
          </button>
        </div>
      </div>
    </section>
  );
}

function isUuid(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value,
  );
}
