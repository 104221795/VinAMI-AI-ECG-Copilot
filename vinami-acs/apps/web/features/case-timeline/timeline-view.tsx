"use client";

import { useMemo, useState } from "react";
import {
  EmptyState,
  StatusBadge,
  TechnicalDetailsDisclosure,
  TimelineItem,
} from "@vinami/ui";
import type { TimelineEventPageView } from "@web/entities/timeline-event/model";
import { formatTimestamp, shortReference } from "@web/shared/formatting";
import { viClinicalTerm, viEventTitle } from "@web/shared/locale/vi";

export function TimelineView({ value }: { value: TimelineEventPageView }) {
  const [order, setOrder] = useState<"newest" | "oldest">("newest");
  const [status, setStatus] = useState("all");
  const events = value.items;
  const ordered = useMemo(
    () =>
      events
        .filter(
          (event) => status === "all" || event.correctionStatus === status,
        )
        .sort((left, right) =>
          order === "newest"
            ? right.occurredAt.localeCompare(left.occurredAt)
            : left.occurredAt.localeCompare(right.occurredAt),
        ),
    [events, order, status],
  );
  if (!events.length)
    return (
      <EmptyState
        title="Projection dòng thời gian đang chờ"
        description="Sự kiện vòng đời đã commit có thể vẫn đang được xử lý. Hãy làm mới sau khi worker hoàn tất projection."
      />
    );
  return (
    <section className="vm-card">
      <header className="vm-card__header">
        <h2>Sự kiện vòng đời đã lưu</h2>
        <label className="vm-field">
          <span>Thứ tự</span>
          <select
            value={order}
            onChange={(event) =>
              setOrder(event.target.value as "newest" | "oldest")
            }
          >
            <option value="newest">Mới nhất trước</option>
            <option value="oldest">Cũ nhất trước</option>
          </select>
        </label>
        <label className="vm-field">
          <span>Trạng thái lịch sử</span>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="all">Tất cả</option>
            <option value="original">Bản gốc</option>
            <option value="correction">Chỉnh sửa</option>
            <option value="revocation">Thu hồi</option>
          </select>
        </label>
      </header>
      <div className="vm-card__body">
        <p className="vm-muted">
          Đang hiển thị {ordered.length} / {value.total} sự kiện do backend
          projection. Dòng thời gian được tạo từ sự kiện backend đã lưu, không
          phải state frontend.
        </p>
        <ol className="vm-timeline">
          {ordered.map((event, index) => (
            <TimelineItem
              key={event.id}
              title={viEventTitle(event.eventType, event.title)}
              timestamp={formatTimestamp(event.occurredAt)}
              actor={
                event.actorId
                  ? shortReference(event.actorId, "ACT")
                  : "Hệ thống"
              }
              last={index === ordered.length - 1}
              detail={
                <TechnicalDetailsDisclosure>
                  <dl>
                    <dt>Trạng thái lịch sử</dt>
                    <dd>
                      <StatusBadge status={event.correctionStatus} />
                    </dd>
                    <dt>Loại sự kiện</dt>
                    <dd>{event.eventType}</dd>
                    <dt>Ghi nhận</dt>
                    <dd>{formatTimestamp(event.recordedAt)}</dd>
                    <dt>Bản ghi nguồn</dt>
                    <dd>
                      <code>{event.sourceRecordId ?? "Chưa cung cấp"}</code>
                    </dd>
                    <dt>Phiên bản nguồn</dt>
                    <dd>{event.sourceRecordVersion ?? "Chưa cung cấp"}</dd>
                    <dt>Phân loại dữ liệu</dt>
                    <dd>{viClinicalTerm(event.dataClassification)}</dd>
                    <dt>Nguồn</dt>
                    <dd>{viClinicalTerm(event.source)}</dd>
                    <dt>Correlation</dt>
                    <dd>
                      <code>{event.correlationId}</code>
                    </dd>
                    <dt>Causation</dt>
                    <dd>
                      <code>{event.causationId ?? "Không có"}</code>
                    </dd>
                  </dl>
                </TechnicalDetailsDisclosure>
              }
            />
          ))}
        </ol>
      </div>
    </section>
  );
}
