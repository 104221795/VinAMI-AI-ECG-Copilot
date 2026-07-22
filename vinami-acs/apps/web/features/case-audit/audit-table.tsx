import {
  EmptyState,
  StatusBadge,
  TechnicalDetailsDisclosure,
} from "@vinami/ui";
import type { AuditEntryPageView } from "@web/entities/audit-entry/model";
import { formatTimestamp } from "@web/shared/formatting";

export function AuditTable({ value }: { value: AuditEntryPageView }) {
  const entries = value.items;
  if (!entries.length)
    return (
      <EmptyState
        title="Chưa có bản ghi kiểm chứng được projection"
        description="Projection audit bất biến có thể vẫn đang xử lý. Frontend không tạo bản ghi audit."
      />
    );
  return (
    <div
      className="vm-table-wrap"
      style={{
        borderTop: "1px solid var(--border)",
        borderRadius: "var(--radius-md)",
      }}
    >
      <p className="vm-muted">
        Đang hiển thị {entries.length} / {value.total} bản ghi audit ghi nối
        tiếp. Các lệnh hệ quả có kèm người thực hiện, ủy quyền và idempotency
        khi có.
      </p>
      <table
        className="vm-table vm-audit-table"
        aria-label="Lịch sử kiểm chứng bất biến của ca"
      >
        <thead>
          <tr>
            <th scope="col">Thời gian</th>
            <th scope="col">Người thực hiện</th>
            <th scope="col">Vai trò</th>
            <th scope="col">Hành động</th>
            <th scope="col">Tài nguyên</th>
            <th scope="col">Kết quả</th>
            <th scope="col">Phiên bản</th>
            <th scope="col">Nguồn</th>
            <th scope="col">Chi tiết</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.id}>
              <td className="vm-tabular">{formatTimestamp(entry.timestamp)}</td>
              <td>{entry.actor}</td>
              <td>{entry.actorRole}</td>
              <td>{entry.action}</td>
              <td>{entry.resource}</td>
              <td>
                <StatusBadge status={entry.outcome} />
              </td>
              <td>
                {entry.priorVersion ?? "-"} → {entry.resultingVersion ?? "-"}
              </td>
              <td>{entry.requestSource}</td>
              <td>
                <TechnicalDetailsDisclosure>
                  <dl>
                    <dt>Correlation</dt>
                    <dd>
                      <code>{entry.correlationId}</code>
                    </dd>
                    <dt>Causation</dt>
                    <dd>
                      <code>{entry.causationId ?? "Không có"}</code>
                    </dd>
                    <dt>Nhà cung cấp danh tính</dt>
                    <dd>{entry.identityProvider ?? "Chưa cung cấp"}</dd>
                    <dt>Xác thực</dt>
                    <dd>{entry.authenticationMethod ?? "Chưa cung cấp"}</dd>
                    <dt>Ủy quyền</dt>
                    <dd>{entry.authorizationResult ?? "Chưa cung cấp"}</dd>
                    <dt>Khóa idempotency</dt>
                    <dd>
                      <code>{entry.idempotencyKey ?? "Chưa cung cấp"}</code>
                    </dd>
                    <dt>Trạng thái chỉnh sửa</dt>
                    <dd>{entry.correctionStatus}</dd>
                    <dt>Phiên bản bản ghi nguồn</dt>
                    <dd>{entry.sourceRecordVersion ?? "Chưa cung cấp"}</dd>
                    <dt>UUID tài nguyên</dt>
                    <dd>
                      <code>{entry.resourceId}</code>
                    </dd>
                    <dt>Lý do</dt>
                    <dd>{entry.reason ?? "Chưa cung cấp"}</dd>
                  </dl>
                </TechnicalDetailsDisclosure>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
