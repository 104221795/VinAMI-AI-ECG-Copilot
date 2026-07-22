"use client";

import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Clock3, Info } from "lucide-react";
import { StatusBadge } from "@vinami/ui";
import { viEvidence } from "@web/shared/locale/vi";

export interface EvidenceStatusSummaryProps {
  title?: string;
  status?: string;
  freshness?: Record<string, string>;
  missingEvidence?: string[];
  staleEvidence?: string[];
  technicalLimits?: string[];
  compact?: boolean;
}

export function EvidenceStatusSummary({
  title = "Trạng thái bằng chứng",
  status,
  freshness = {},
  missingEvidence = [],
  staleEvidence = [],
  technicalLimits = [],
  compact = false,
}: EvidenceStatusSummaryProps) {
  const hasGaps =
    missingEvidence.length > 0 ||
    staleEvidence.length > 0 ||
    technicalLimits.length > 0;
  const freshnessEntries = Object.entries(freshness);

  return (
    <section
      className={`vm-evidence-summary${compact ? " vm-evidence-summary--compact" : ""}`}
      aria-label={title}
    >
      <div className="vm-evidence-summary__header">
        <h3>{title}</h3>
        {status ? <StatusBadge status={status} /> : null}
      </div>

      {freshnessEntries.length > 0 && (
        <div
          className="vm-evidence-summary__freshness"
          aria-label="Độ mới của bằng chứng theo nguồn"
        >
          {freshnessEntries.map(([source, sourceStatus]) => (
            <span key={source}>
              <strong>{viEvidence(source)}</strong>
              <StatusBadge status={sourceStatus} />
            </span>
          ))}
        </div>
      )}

      {hasGaps ? (
        <div className="vm-evidence-summary__items">
          {missingEvidence.length > 0 && (
            <EvidenceIssue
              icon={<Info size={16} aria-hidden />}
              label="Thiếu hoặc chưa rõ"
              items={missingEvidence.map(viEvidence)}
              tone="neutral"
            />
          )}
          {staleEvidence.length > 0 && (
            <EvidenceIssue
              icon={<Clock3 size={16} aria-hidden />}
              label="Bằng chứng đã cũ"
              items={staleEvidence.map(viEvidence)}
              tone="stale"
            />
          )}
          {technicalLimits.length > 0 && (
            <EvidenceIssue
              icon={<AlertTriangle size={16} aria-hidden />}
              label="Giới hạn kỹ thuật"
              items={technicalLimits}
              tone="warning"
            />
          )}
          <p className="vm-evidence-summary__note">
            Dữ liệu thiếu hoặc chưa rõ là dữ liệu chưa đầy đủ, không phải bằng
            chứng âm tính.
          </p>
        </div>
      ) : (
        <p className="vm-evidence-summary__ok">
          <CheckCircle2 size={16} aria-hidden /> Không ghi nhận bằng chứng
          thiếu, cũ hoặc giới hạn kỹ thuật.
        </p>
      )}
    </section>
  );
}

function EvidenceIssue({
  icon,
  label,
  items,
  tone,
}: {
  icon: ReactNode;
  label: string;
  items: string[];
  tone: "neutral" | "stale" | "warning";
}) {
  return (
    <div className={`vm-evidence-issue vm-evidence-issue--${tone}`}>
      {icon}
      <div>
        <strong>{label}</strong>
        <span>{items.join(", ")}</span>
      </div>
    </div>
  );
}
