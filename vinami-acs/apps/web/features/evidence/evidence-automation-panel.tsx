"use client";

import { Layers3, ListChecks, ShieldAlert } from "lucide-react";
import { StatusBadge } from "@vinami/ui";
import { formatDueLabel } from "@web/shared/formatting";
import {
  viEvidence,
  viSafetyNotice,
  viStatus,
  viTaskType,
} from "@web/shared/locale/vi";

export interface EvidenceAutomationPanelProps {
  automation?: Record<string, unknown>;
  compact?: boolean;
  showAlertDigest?: boolean;
}

export function EvidenceAutomationPanel({
  automation,
  compact = false,
  showAlertDigest = true,
}: EvidenceAutomationPanelProps) {
  if (!automation) return null;
  const completeness = record(automation.completeness);
  const suggestions = list(automation.suggested_tasks);
  const digest = list(automation.alert_digest);
  return (
    <section
      className={`vm-automation-panel${compact ? " vm-automation-panel--compact" : ""}`}
      aria-label="Độ đầy đủ bằng chứng và gợi ý tự động hóa"
    >
      <div className="vm-automation-score">
        <Layers3 size={18} aria-hidden="true" />
        <div>
          <strong>{number(completeness.score)}%</strong>
          <span>
            Độ đầy đủ bằng chứng -{" "}
            {viStatus(text(completeness.status, "unknown"))}
          </span>
          <small>
            {number(completeness.current_count)} /{" "}
            {number(completeness.required_count)} nhóm bằng chứng bắt buộc đang
            hiện hành.
          </small>
        </div>
        <StatusBadge status={text(completeness.status, "unknown")} />
      </div>

      <div className="vm-suggested-task-list">
        <h4>
          <ListChecks size={15} aria-hidden="true" /> Gợi ý công việc từ backend
        </h4>
        {suggestions.length ? (
          suggestions.slice(0, compact ? 3 : 6).map((item) => (
            <article key={text(item.suggestion_id)}>
              <div>
                <strong>{viTaskType(text(item.task_type))}</strong>
                <p>{text(item.reason)}</p>
                <small>
                  {array(item.evidence_gaps).map(viEvidence).join(", ")}
                </small>
              </div>
              <span>
                <StatusBadge status={text(item.due_state)} />
                <small>{formatDueLabel(text(item.due_at, ""))}</small>
              </span>
            </article>
          ))
        ) : (
          <p className="vm-inline-empty">
            Chưa có công việc gợi ý. Tiếp tục xử lý trong các không gian do bác
            sĩ phụ trách.
          </p>
        )}
      </div>

      {showAlertDigest && (
        <div className="vm-alert-digest">
          <h4>
            <ShieldAlert size={15} aria-hidden="true" /> Tóm tắt cảnh báo
          </h4>
          {digest.length ? (
            digest.slice(0, compact ? 3 : 6).map((item) => (
              <article key={text(item.group_key)}>
                <div>
                  <strong>{viStatus(text(item.alert_type))}</strong>
                  <p>{text(item.message)}</p>
                  <small>
                    {number(item.count)} cảnh báo -{" "}
                    {viStatus(text(item.source))}
                  </small>
                </div>
                <StatusBadge status={text(item.severity)} />
              </article>
            ))
          ) : (
            <p className="vm-inline-empty">
              Không có nhóm cảnh báo chưa xử lý trong góc nhìn này.
            </p>
          )}
        </div>
      )}

      {!compact && (
        <p className="vm-automation-notice">
          {viSafetyNotice(text(automation.safety_notice))}
        </p>
      )}
    </section>
  );
}

export function AlertDigestPanel({
  digest,
  compact = false,
}: {
  digest?: Record<string, unknown>[];
  compact?: boolean;
}) {
  const groups = digest ?? [];
  return (
    <section
      className={`vm-alert-digest${compact ? " vm-alert-digest--compact" : ""}`}
      aria-label="Tóm tắt cảnh báo theo nhóm"
    >
      <h4>
        <ShieldAlert size={15} aria-hidden="true" /> Tóm tắt cảnh báo
      </h4>
      {groups.length ? (
        groups.slice(0, compact ? 3 : 8).map((item) => (
          <article key={text(item.group_key)}>
            <div>
              <strong>{viStatus(text(item.alert_type))}</strong>
              <p>{text(item.message)}</p>
              <small>
                {number(item.count)} cảnh báo - {viStatus(text(item.source))}
              </small>
            </div>
            <StatusBadge status={text(item.severity)} />
          </article>
        ))
      ) : (
        <p className="vm-inline-empty">
          Không có nhóm cảnh báo chưa xử lý trong góc nhìn này.
        </p>
      )}
    </section>
  );
}

function record(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function list(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

function array(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => text(item)) : [];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(value: unknown, fallback = "Chưa ghi nhận") {
  return typeof value === "string" && value.length ? value : fallback;
}

function number(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}
