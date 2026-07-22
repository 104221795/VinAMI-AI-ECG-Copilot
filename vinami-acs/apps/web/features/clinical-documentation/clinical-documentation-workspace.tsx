"use client";

import type {
  CorrectTriageInput,
  CorrectVitalsInput,
  RecordTriageInput,
  RecordVitalsInput,
} from "@vinami/api-client";
import {
  Badge,
  Button,
  ClinicalCard,
  EmptyState,
  TechnicalDetailsDisclosure,
} from "@vinami/ui";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import type {
  ClinicalDocumentationView,
  ObservationState,
  TriageAssessmentView,
  VitalObservationSetView,
} from "@web/entities/clinical-documentation/model";
import { createBrowserApiClient } from "@web/shared/api/browser";
import { formatTimestamp, shortReference } from "@web/shared/formatting";
import {
  viClinicalLabel,
  viObservationState,
  viStatus,
} from "@web/shared/locale/vi";
import { TriageForm, type TriageFormValue } from "./triage-form";
import { VitalForm, type VitalFormValue } from "./vital-form";

type Editor =
  "triage-new" | "triage-correction" | "vitals-new" | "vitals-correction";

export function ClinicalDocumentationWorkspace({
  caseId,
  value,
}: {
  caseId: string;
  value: ClinicalDocumentationView;
}) {
  const router = useRouter();
  const api = useRef(createBrowserApiClient());
  const idempotencyKey = useRef(crypto.randomUUID());
  const [editor, setEditor] = useState<Editor | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submitTriage(form: TriageFormValue) {
    setBusy(true);
    setError(null);
    try {
      const content = triagePayload(form);
      if (editor === "triage-correction" && value.currentTriage) {
        const body: CorrectTriageInput = {
          ...content,
          expected_record_version: value.currentTriage.recordVersion,
          correction_reason: form.correctionReason,
        };
        await api.current.correctTriage(
          caseId,
          value.currentTriage.assessmentId,
          body,
          idempotencyKey.current,
        );
        setMessage("Đã ghi nhận chỉnh sửa tiếp nhận thành phiên bản mới.");
      } else {
        const body: RecordTriageInput = {
          ...content,
          expected_case_version: value.caseVersion,
        };
        await api.current.recordTriage(caseId, body, idempotencyKey.current);
        setMessage("Đã ghi nhận đánh giá tiếp nhận.");
      }
      finishMutation();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Không thể hoàn tất yêu cầu.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function submitVitals(form: VitalFormValue) {
    const measurements = vitalMeasurements(form);
    if (measurements.length === 0) {
      setError("Nhập ít nhất một chỉ số sinh hiệu trước khi rà soát.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const observedAt = new Date(form.observedAt).toISOString();
      const content = {
        observed_at: observedAt,
        source: "vinami-next-clinical-workspace",
        measurements,
        supplemental_oxygen_state: "not_assessed" as const,
      };
      if (editor === "vitals-correction" && value.latestVitals) {
        const body: CorrectVitalsInput = {
          ...content,
          expected_record_version: value.latestVitals.recordVersion,
          correction_reason: form.correctionReason,
        };
        await api.current.correctVitals(
          caseId,
          value.latestVitals.vitalSetId,
          body,
          idempotencyKey.current,
        );
        setMessage("Đã ghi nhận chỉnh sửa sinh hiệu thành phiên bản mới.");
      } else {
        const body: RecordVitalsInput = {
          ...content,
          expected_case_version: value.caseVersion,
        };
        await api.current.recordVitals(caseId, body, idempotencyKey.current);
        setMessage("Đã ghi nhận bộ sinh hiệu.");
      }
      finishMutation();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Không thể hoàn tất yêu cầu.",
      );
    } finally {
      setBusy(false);
    }
  }

  function finishMutation() {
    idempotencyKey.current = crypto.randomUUID();
    setEditor(null);
    router.refresh();
  }

  function open(next: Editor) {
    idempotencyKey.current = crypto.randomUUID();
    setError(null);
    setMessage(null);
    setEditor(next);
  }

  return (
    <section
      className="vm-documentation"
      aria-labelledby="documentation-heading"
    >
      <header className="vm-documentation__header">
        <div>
          <p className="vm-eyebrow">Luồng dọc R2 đã xác thực</p>
          <h2 id="documentation-heading">Ghi nhận tiếp nhận và sinh hiệu</h2>
          <p>
            Chỉ ghi nhận quan sát có cấu trúc. Không suy luận chẩn đoán, hướng
            xử trí hoặc ngưỡng lâm sàng.
          </p>
        </div>
        <Badge tone={value.missingDocumentation.length ? "warning" : "success"}>
          {value.missingDocumentation.length
            ? `${value.missingDocumentation.length} mục ghi nhận còn thiếu`
            : "Đã đủ theo chính sách ghi nhận"}
        </Badge>
      </header>

      {value.missingDocumentation.length > 0 && (
        <div className="vm-documentation-gaps" role="status">
          <strong>Rà soát độ đầy đủ ghi nhận</strong>
          <ul>
            {value.missingDocumentation.map((item) => (
              <li key={item.identifier}>{item.description}</li>
            ))}
          </ul>
          <small>
            Chính sách backend {value.completenessPolicyVersion}; chưa gán ý
            nghĩa lâm sàng.
          </small>
        </div>
      )}
      {message && (
        <div className="vm-banner vm-banner--success" role="status">
          {message}
        </div>
      )}
      {error && (
        <div className="vm-banner vm-banner--critical" role="alert">
          {error}
        </div>
      )}

      <div className="vm-documentation-grid">
        <ClinicalCard
          title="Tiếp nhận có cấu trúc"
          action={
            editor?.startsWith("triage") ? null : value.currentTriage ? (
              <Button type="button" onClick={() => open("triage-correction")}>
                Chỉnh sửa bản ghi
              </Button>
            ) : (
              <Button
                type="button"
                className="vm-button--primary"
                onClick={() => open("triage-new")}
              >
                Ghi nhận tiếp nhận
              </Button>
            )
          }
        >
          {editor?.startsWith("triage") ? (
            <TriageForm
              current={
                editor === "triage-correction" ? value.currentTriage : null
              }
              busy={busy}
              onCancel={() => setEditor(null)}
              onSubmit={submitTriage}
            />
          ) : value.currentTriage ? (
            <TriageCurrent value={value.currentTriage} />
          ) : (
            <EmptyState
              title="Chưa ghi nhận đánh giá tiếp nhận"
              description="Ghi rõ trạng thái có, không có, chưa rõ hoặc chưa đánh giá."
            />
          )}
        </ClinicalCard>

        <ClinicalCard
          title="Sinh hiệu"
          action={
            editor?.startsWith("vitals") ? null : (
              <div className="vm-card-actions">
                {value.latestVitals && (
                  <Button
                    type="button"
                    onClick={() => open("vitals-correction")}
                  >
                    Chỉnh sửa bản mới nhất
                  </Button>
                )}
                <Button
                  type="button"
                  className="vm-button--primary"
                  onClick={() => open("vitals-new")}
                >
                  Ghi nhận bộ mới
                </Button>
              </div>
            )
          }
        >
          {editor?.startsWith("vitals") ? (
            <VitalForm
              current={
                editor === "vitals-correction" ? value.latestVitals : null
              }
              busy={busy}
              onCancel={() => setEditor(null)}
              onSubmit={submitVitals}
            />
          ) : value.latestVitals ? (
            <VitalCurrent value={value.latestVitals} />
          ) : (
            <EmptyState
              title="Chưa có bộ sinh hiệu"
              description="Ghi nhận giá trị thô kèm thời gian, đơn vị và nguồn rõ ràng."
            />
          )}
        </ClinicalCard>
      </div>

      <ClinicalCard title="Lịch sử phiên bản ghi nhận">
        <div className="vm-revision-grid">
          <RevisionList
            title="Phiên bản tiếp nhận"
            values={value.triageHistory}
            type="triage"
          />
          <RevisionList
            title="Phiên bản bộ sinh hiệu"
            values={value.vitalHistory}
            type="vitals"
          />
        </div>
        <TechnicalDetailsDisclosure title="Nguồn gốc dữ liệu">
          <p>
            Dữ liệu làm mới {formatTimestamp(value.dataFreshnessAt)}. Phiên bản
            aggregate của ca {value.caseVersion}. Chỉnh sửa được ghi nối tiếp và
            hiển thị trong Dòng thời gian/Nhật ký kiểm chứng sau khi outbox xử
            lý.
          </p>
        </TechnicalDetailsDisclosure>
      </ClinicalCard>
    </section>
  );
}

function TriageCurrent({ value }: { value: TriageAssessmentView }) {
  return (
    <div className="vm-current-record">
      <div className="vm-record-meta">
        <Badge tone={value.status === "correction" ? "warning" : "info"}>
          Phiên bản {value.revisionNumber} · {viStatus(value.status)}
        </Badge>
        <span>
          Ghi nhận {formatTimestamp(value.recordedAt)} bởi {value.recordedBy}
        </span>
      </div>
      <dl className="vm-definition-list">
        <dt>Lý do vào viện</dt>
        <dd>{value.chiefComplaint ?? "Chưa ghi nhận"}</dd>
        <dt>Khởi phát</dt>
        <dd>
          {stateLabel(value.symptomOnsetState)}
          {value.symptomOnsetAt
            ? ` · ${formatTimestamp(value.symptomOnsetAt)}`
            : ""}
        </dd>
        <dt>Mô tả</dt>
        <dd>{value.symptomDescription ?? "Chưa ghi nhận"}</dd>
      </dl>
      <ObservationRows
        title="Triệu chứng đi kèm"
        values={value.associatedSymptoms}
      />
      <ObservationRows
        title="Tiền sử / yếu tố nguy cơ"
        values={value.riskFactors}
      />
      {value.correctionReason && (
        <p className="vm-correction-note">
          <strong>Lý do chỉnh sửa:</strong> {value.correctionReason}
        </p>
      )}
    </div>
  );
}

function VitalCurrent({ value }: { value: VitalObservationSetView }) {
  return (
    <div className="vm-current-record">
      <div className="vm-record-meta">
        <Badge tone={value.correctionReason ? "warning" : "info"}>
          Bộ {value.sequenceNumber} · phiên bản {value.revisionNumber}
        </Badge>
        <span>Quan sát {formatTimestamp(value.observedAt)}</span>
      </div>
      <div className="vm-vital-values">
        {value.measurements.map((item) => (
          <div key={item.kind}>
            <span>{viClinicalLabel(item.kind)}</span>
            <strong>
              {item.value} <small>{item.unit}</small>
            </strong>
            <small>{viStatus(item.qualityStatus)}</small>
          </div>
        ))}
      </div>
      {value.correctionReason && (
        <p className="vm-correction-note">
          <strong>Lý do chỉnh sửa:</strong> {value.correctionReason}
        </p>
      )}
    </div>
  );
}

function ObservationRows({
  title,
  values,
}: {
  title: string;
  values: TriageAssessmentView["associatedSymptoms"];
}) {
  if (!values.length) return null;
  return (
    <div className="vm-observation-list">
      <strong>{title}</strong>
      {values.map((item) => (
        <span key={item.name}>
          {viClinicalLabel(item.name)}
          <Badge tone={item.state === "present" ? "info" : "neutral"}>
            {stateLabel(item.state)}
          </Badge>
        </span>
      ))}
    </div>
  );
}

function RevisionList({
  title,
  values,
  type,
}: {
  title: string;
  values: Array<TriageAssessmentView | VitalObservationSetView>;
  type: "triage" | "vitals";
}) {
  return (
    <div>
      <h3>{title}</h3>
      {values.length ? (
        <ol className="vm-revision-list">
          {values.map((item) => (
            <li
              key={
                type === "triage"
                  ? (item as TriageAssessmentView).assessmentId
                  : (item as VitalObservationSetView).vitalSetId
              }
            >
              <strong>Phiên bản {item.revisionNumber}</strong>
              <span>
                {formatTimestamp(item.recordedAt)} · {item.recordedBy}
              </span>
              <small>
                {type === "triage"
                  ? shortReference(
                      (item as TriageAssessmentView).assessmentId,
                      "TRI",
                    )
                  : `Bộ ${(item as VitalObservationSetView).sequenceNumber}`}
              </small>
            </li>
          ))}
        </ol>
      ) : (
        <p>Chưa ghi nhận phiên bản.</p>
      )}
    </div>
  );
}

function triagePayload(
  form: TriageFormValue,
): Omit<RecordTriageInput, "expected_case_version"> {
  return {
    occurred_at: new Date().toISOString(),
    source: "vinami-next-clinical-workspace",
    chief_complaint: form.chiefComplaint || null,
    symptom_description: form.symptomDescription || null,
    symptom_onset_state: form.onsetState,
    symptom_onset_at:
      form.onsetState === "present"
        ? new Date(form.onsetAt).toISOString()
        : null,
    symptom_onset_precision:
      form.onsetState === "present" ? form.onsetPrecision : null,
    associated_symptoms: [
      { name: "dyspnoea", state: form.dyspnoea, note: null },
      { name: "nausea", state: form.nausea, note: null },
    ],
    cardiovascular_risk_factors: [
      { name: "smoking history", state: form.smokingHistory, note: null },
      { name: "diabetes history", state: form.diabetesHistory, note: null },
    ],
  };
}

function vitalMeasurements(
  form: VitalFormValue,
): RecordVitalsInput["measurements"] {
  const observedAt = new Date(form.observedAt).toISOString();
  const definitions = [
    ["heart_rate", form.heartRate, "beats/min"],
    ["systolic_blood_pressure", form.systolicBloodPressure, "mmHg"],
    ["diastolic_blood_pressure", form.diastolicBloodPressure, "mmHg"],
    ["respiratory_rate", form.respiratoryRate, "breaths/min"],
    ["oxygen_saturation", form.oxygenSaturation, "%"],
    ["body_temperature", form.bodyTemperature, "degC"],
    ["pain_score", form.painScore, "score"],
  ] as const;
  return definitions
    .filter(([, raw]) => raw.trim() !== "")
    .map(([kind, raw, unit]) => ({
      kind,
      value: Number(raw),
      unit,
      source: "vinami-next-clinical-workspace",
      observed_at: observedAt,
      quality_status: "unknown",
    }));
}

function stateLabel(value: ObservationState) {
  return viObservationState(value);
}
