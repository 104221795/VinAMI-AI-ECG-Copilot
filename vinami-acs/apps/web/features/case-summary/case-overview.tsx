import { ClinicalCard, TimelineItem } from "@vinami/ui";
import type { CaseWorkspaceView } from "@web/entities/clinical-case/model";
import type { TimelineEventView } from "@web/entities/timeline-event/model";
import {
  formatRelative,
  formatTimestamp,
  shortReference,
} from "@web/shared/formatting";
import { viPriority, viStatus } from "@web/shared/locale/vi";

export function CaseOverview({
  value,
  timeline,
}: {
  value: CaseWorkspaceView;
  timeline: TimelineEventView[];
}) {
  const latest = [...timeline].sort((left, right) =>
    right.occurredAt.localeCompare(left.occurredAt),
  )[0];
  return (
    <div className="vm-section-stack">
      <section className="vm-summary-grid" aria-label="Tóm tắt ca">
        <div className="vm-summary-block">
          <span>Trạng thái vòng đời hiện tại</span>
          <strong>{viStatus(value.status)}</strong>
          <p>Trạng thái điều phối, không phải chẩn đoán</p>
        </div>
        <div className="vm-summary-block">
          <span>Ưu tiên lâm sàng</span>
          <strong>{viPriority(value.priority)}</strong>
          <p>Được ghi nhận bởi lệnh vòng đời</p>
        </div>
        <div className="vm-summary-block">
          <span>Thời điểm đến</span>
          <strong>{formatRelative(value.arrivalAt)}</strong>
          <p>{formatTimestamp(value.arrivalAt)}</p>
        </div>
        <div className="vm-summary-block">
          <span>Vị trí tiếp nhận</span>
          <strong>{value.location}</strong>
          <p>Tiếp nhận {viStatus(value.encounterStatus)}</p>
        </div>
        <div className="vm-summary-block">
          <span>Mở ca</span>
          <strong>{formatRelative(value.openedAt)}</strong>
          <p>{formatTimestamp(value.openedAt)}</p>
        </div>
        <div className="vm-summary-block">
          <span>Cập nhật đã lưu gần nhất</span>
          <strong>{formatRelative(value.updatedAt)}</strong>
          <p>Phiên bản aggregate {value.aggregateVersion}</p>
        </div>
      </section>
      <div className="vm-layout-split">
        <ClinicalCard title="Bệnh nhân và lần tiếp nhận">
          <dl className="vm-definition-list">
            <dt>Mã bệnh nhân</dt>
            <dd>{value.patientReference}</dd>
            <dt>Thông tin nhân khẩu học an toàn</dt>
            <dd>{value.demographics}</dd>
            <dt>Hệ thống tham chiếu</dt>
            <dd>{value.patientReferenceSystem}</dd>
            <dt>Mã tiếp nhận</dt>
            <dd>{value.encounterReference}</dd>
            <dt>Vị trí</dt>
            <dd>{value.location}</dd>
            <dt>Thời điểm đến</dt>
            <dd>{formatTimestamp(value.arrivalAt)}</dd>
          </dl>
        </ClinicalCard>
        <ClinicalCard title="Hoạt động vòng đời gần nhất">
          {latest ? (
            <ol className="vm-timeline">
              <TimelineItem
                title={latest.title}
                timestamp={formatTimestamp(latest.occurredAt)}
                actor={
                  latest.actorId
                    ? shortReference(latest.actorId, "ACT")
                    : "Hệ thống"
                }
                last
                detail={<p>Nguồn projection: {latest.source}</p>}
              />
            </ol>
          ) : (
            <p>
              Projection vòng đời có thể vẫn đang xử lý. Dùng Dòng thời gian để
              làm mới.
            </p>
          )}
        </ClinicalCard>
      </div>
      <ClinicalCard title="Ngữ cảnh mở ca">
        <p>{value.openingReason}</p>
      </ClinicalCard>
      <section className="vm-capabilities">
        <strong>Năng lực chưa bật:</strong> Troponin nối tiếp, tổng hợp lâm
        sàng, công việc và cảnh báo vẫn nằm ngoài lát cắt R3 đã xác thực. Không
        suy luận dữ liệu lâm sàng tại đây.
      </section>
    </div>
  );
}
