"use client";

import { Button, ConfirmationDialog } from "@vinami/ui";
import { useForm } from "react-hook-form";
import type {
  ObservationState,
  TriageAssessmentView,
} from "@web/entities/clinical-documentation/model";

const states: Array<{ value: ObservationState; label: string }> = [
  { value: "present", label: "Có" },
  { value: "absent", label: "Không có" },
  { value: "unknown", label: "Chưa rõ" },
  { value: "not_assessed", label: "Chưa đánh giá" },
];

export interface TriageFormValue {
  chiefComplaint: string;
  symptomDescription: string;
  onsetState: ObservationState;
  onsetAt: string;
  onsetPrecision: "exact" | "approximate" | "date_only" | "unknown";
  dyspnoea: ObservationState;
  nausea: ObservationState;
  smokingHistory: ObservationState;
  diabetesHistory: ObservationState;
  correctionReason: string;
}

export function TriageForm({
  current,
  busy,
  onCancel,
  onSubmit,
}: {
  current: TriageAssessmentView | null;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (value: TriageFormValue) => Promise<void>;
}) {
  const correcting = current !== null;
  const { register, watch, handleSubmit, formState } = useForm<TriageFormValue>(
    {
      defaultValues: {
        chiefComplaint: current?.chiefComplaint ?? "",
        symptomDescription: current?.symptomDescription ?? "",
        onsetState: current?.symptomOnsetState ?? "not_assessed",
        onsetAt: current?.symptomOnsetAt
          ? toLocalDateTime(current.symptomOnsetAt)
          : "",
        onsetPrecision:
          (current?.symptomOnsetPrecision as TriageFormValue["onsetPrecision"]) ??
          "unknown",
        dyspnoea: observation(current, "dyspnoea"),
        nausea: observation(current, "nausea"),
        smokingHistory: risk(current, "smoking history"),
        diabetesHistory: risk(current, "diabetes history"),
        correctionReason: "",
      },
    },
  );
  const onsetState = watch("onsetState");
  const correctionReason = watch("correctionReason");
  const canReview = !correcting || correctionReason.trim().length > 0;

  return (
    <form
      className="vm-clinical-form"
      onSubmit={(event) => event.preventDefault()}
    >
      <div className="vm-form-grid">
        <label className="vm-input-field vm-form-span-2">
          <span>Lý do vào viện</span>
          <textarea rows={2} {...register("chiefComplaint")} />
        </label>
        <label className="vm-input-field vm-form-span-2">
          <span>Mô tả triệu chứng do người bệnh cung cấp</span>
          <textarea rows={3} {...register("symptomDescription")} />
        </label>
        <label className="vm-input-field">
          <span>Trạng thái thời điểm khởi phát</span>
          <select {...register("onsetState")}>
            {states.map((state) => (
              <option key={state.value} value={state.value}>
                {state.label}
              </option>
            ))}
          </select>
        </label>
        {onsetState === "present" && (
          <>
            <label className="vm-input-field">
              <span>Thời điểm khởi phát được khai báo</span>
              <input
                type="datetime-local"
                required
                {...register("onsetAt", { required: true })}
              />
            </label>
            <label className="vm-input-field">
              <span>Độ chính xác thời gian</span>
              <select {...register("onsetPrecision")}>
                <option value="exact">Chính xác</option>
                <option value="approximate">Ước lượng</option>
                <option value="date_only">Chỉ biết ngày</option>
                <option value="unknown">Chưa rõ độ chính xác</option>
              </select>
            </label>
          </>
        )}
      </div>
      <fieldset className="vm-observation-fieldset">
        <legend>Ghi nhận triệu chứng đi kèm</legend>
        <ObservationSelect
          label="Khó thở"
          registration={register("dyspnoea")}
        />
        <ObservationSelect label="Buồn nôn" registration={register("nausea")} />
      </fieldset>
      <fieldset className="vm-observation-fieldset">
        <legend>Ghi nhận tiền sử tim mạch/yếu tố nguy cơ</legend>
        <ObservationSelect
          label="Tiền sử hút thuốc"
          registration={register("smokingHistory")}
        />
        <ObservationSelect
          label="Tiền sử đái tháo đường"
          registration={register("diabetesHistory")}
        />
      </fieldset>
      {correcting && (
        <label className="vm-input-field">
          <span>Lý do chỉnh sửa</span>
          <textarea
            rows={2}
            required
            {...register("correctionReason", { required: true })}
          />
          {formState.errors.correctionReason && (
            <small role="alert">Cần nhập lý do chỉnh sửa.</small>
          )}
        </label>
      )}
      <div className="vm-form-actions">
        <Button type="button" onClick={onCancel} disabled={busy}>
          Hủy
        </Button>
        <ConfirmationDialog
          trigger={
            <Button
              type="button"
              className="vm-button--primary"
              disabled={busy || !canReview}
            >
              {busy
                ? "Đang lưu..."
                : correcting
                  ? "Rà soát chỉnh sửa"
                  : "Rà soát thông tin"}
            </Button>
          }
          title={
            correcting ? "Xác nhận chỉnh sửa tiếp nhận" : "Xác nhận tiếp nhận"
          }
          description={
            correcting
              ? "Một phiên bản ghi nối tiếp mới sẽ được tạo. Bản ghi trước vẫn còn trong lịch sử."
              : "Ghi nhận các quan sát thực tế này vào ca lâm sàng?"
          }
          confirmLabel={
            correcting ? "Ghi nhận chỉnh sửa" : "Ghi nhận tiếp nhận"
          }
          onConfirm={handleSubmit(onSubmit)}
        />
      </div>
    </form>
  );
}

function ObservationSelect({
  label,
  registration,
}: {
  label: string;
  registration: ReturnType<
    ReturnType<typeof useForm<TriageFormValue>>["register"]
  >;
}) {
  return (
    <label className="vm-input-field">
      <span>{label}</span>
      <select {...registration}>
        {states.map((state) => (
          <option key={state.value} value={state.value}>
            {state.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function observation(
  current: TriageAssessmentView | null,
  name: string,
): ObservationState {
  return (
    current?.associatedSymptoms.find((item) => item.name === name)?.state ??
    "not_assessed"
  );
}

function risk(
  current: TriageAssessmentView | null,
  name: string,
): ObservationState {
  return (
    current?.riskFactors.find((item) => item.name === name)?.state ??
    "not_assessed"
  );
}

function toLocalDateTime(value: string): string {
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 16);
}
