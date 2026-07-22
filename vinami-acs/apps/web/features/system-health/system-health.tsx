import {
  Badge,
  ClinicalCard,
  StatusBadge,
  TechnicalDetailsDisclosure,
} from "@vinami/ui";
import type { SystemHealthView } from "./data";
import { formatTimestamp } from "@web/shared/formatting";

function HealthRow({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="vm-health-row">
      <div>
        <strong>{label}</strong>
        {detail && <small>{detail}</small>}
      </div>
      <StatusBadge status={value} />
    </div>
  );
}

export function SystemHealth({ value }: { value: SystemHealthView }) {
  return (
    <div className="vm-health-grid">
      <ClinicalCard title="Dịch vụ ứng dụng">
        <HealthRow
          label="FastAPI liveness"
          value={value.apiStatus}
          detail="Endpoint tiến trình"
        />
        <HealthRow
          label="API readiness"
          value={value.readiness}
          detail="Kiểm tra kèm phụ thuộc"
        />
        <HealthRow
          label="Cơ sở dữ liệu và schema"
          value={value.dependency}
          detail={`Migration ${value.revision}`}
        />
        <HealthRow
          label="Worker"
          value="Chưa công bố"
          detail="R1 chưa công bố hợp đồng health cho worker"
        />
      </ClinicalCard>
      <ClinicalCard title="Nhà cung cấp danh tính">
        <HealthRow
          label="Trạng thái provider"
          value={value.identityStatus}
          detail={value.identityProvider}
        />
        <HealthRow
          label="Chế độ danh tính"
          value={value.identityMode}
          detail={
            value.developmentOnly
              ? "Chỉ dùng danh tính mô phỏng"
              : "Đã xác thực qua provider"
          }
        />
        {value.developmentOnly && (
          <Badge tone="warning">
            Danh tính phát triển không phải xác thực sản xuất
          </Badge>
        )}
        <TechnicalDetailsDisclosure>
          <dl>
            <dt>Lần kiểm tra thành công gần nhất</dt>
            <dd>{formatTimestamp(value.checkedAt)}</dd>
            <dt>Phiên bản schema</dt>
            <dd>
              <code>{value.revision}</code>
            </dd>
          </dl>
        </TechnicalDetailsDisclosure>
      </ClinicalCard>
    </div>
  );
}
