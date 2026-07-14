"use client";

import { Button, ConfirmationDialog } from "@vinami/ui";
import { useForm } from "react-hook-form";
import type { VitalObservationSetView } from "@web/entities/clinical-documentation/model";

export interface VitalFormValue {
  observedAt: string;
  heartRate: string;
  systolicBloodPressure: string;
  diastolicBloodPressure: string;
  respiratoryRate: string;
  oxygenSaturation: string;
  bodyTemperature: string;
  painScore: string;
  correctionReason: string;
}

const fields: Array<{
  name: keyof VitalFormValue;
  label: string;
  unit: string;
}> = [
  { name: "heartRate", label: "Heart rate", unit: "beats/min" },
  { name: "systolicBloodPressure", label: "Systolic BP", unit: "mmHg" },
  { name: "diastolicBloodPressure", label: "Diastolic BP", unit: "mmHg" },
  { name: "respiratoryRate", label: "Respiratory rate", unit: "breaths/min" },
  { name: "oxygenSaturation", label: "Oxygen saturation", unit: "%" },
  { name: "bodyTemperature", label: "Body temperature", unit: "degC" },
  { name: "painScore", label: "Pain score", unit: "score" },
];

export function VitalForm({
  current,
  busy,
  onCancel,
  onSubmit,
}: {
  current: VitalObservationSetView | null;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (value: VitalFormValue) => Promise<void>;
}) {
  const correcting = current !== null;
  const { register, handleSubmit, formState, watch } = useForm<VitalFormValue>({
    defaultValues: {
      observedAt: current
        ? toLocalDateTime(current.observedAt)
        : localDateTime(),
      heartRate: measurement(current, "heart_rate"),
      systolicBloodPressure: measurement(current, "systolic_blood_pressure"),
      diastolicBloodPressure: measurement(current, "diastolic_blood_pressure"),
      respiratoryRate: measurement(current, "respiratory_rate"),
      oxygenSaturation: measurement(current, "oxygen_saturation"),
      bodyTemperature: measurement(current, "body_temperature"),
      painScore: measurement(current, "pain_score"),
      correctionReason: "",
    },
  });
  const correctionReason = watch("correctionReason");
  const canReview = !correcting || correctionReason.trim().length > 0;
  return (
    <form
      className="vm-clinical-form"
      onSubmit={(event) => event.preventDefault()}
    >
      <div className="vm-form-grid vm-vital-grid">
        <label className="vm-input-field vm-form-span-2">
          <span>Observation time</span>
          <input
            type="datetime-local"
            required
            {...register("observedAt", { required: true })}
          />
        </label>
        {fields.map((field) => (
          <label className="vm-input-field" key={field.name}>
            <span>{field.label}</span>
            <div className="vm-unit-input">
              <input
                type="number"
                step="any"
                inputMode="decimal"
                {...register(field.name)}
              />
              <strong>{field.unit}</strong>
            </div>
          </label>
        ))}
      </div>
      <p className="vm-form-note">
        Units are explicit and fixed by the API contract. Blank values are not
        submitted.
      </p>
      {correcting && (
        <label className="vm-input-field">
          <span>Correction reason</span>
          <textarea
            rows={2}
            required
            {...register("correctionReason", { required: true })}
          />
          {formState.errors.correctionReason && (
            <small role="alert">A correction reason is required.</small>
          )}
        </label>
      )}
      <div className="vm-form-actions">
        <Button type="button" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
        <ConfirmationDialog
          trigger={
            <Button
              type="button"
              className="vm-button--primary"
              disabled={busy || !canReview}
            >
              {busy
                ? "Saving…"
                : correcting
                  ? "Review correction"
                  : "Review vital set"}
            </Button>
          }
          title={
            correcting
              ? "Confirm vital correction"
              : "Confirm vital observations"
          }
          description={
            correcting
              ? "A new revision will be appended; the original observations remain auditable."
              : "Record this timestamped observation set in the clinical case?"
          }
          confirmLabel={correcting ? "Record correction" : "Record vital set"}
          onConfirm={handleSubmit(onSubmit)}
        />
      </div>
    </form>
  );
}

function measurement(
  current: VitalObservationSetView | null,
  kind: string,
): string {
  const value = current?.measurements.find((item) => item.kind === kind)?.value;
  return value === undefined ? "" : String(value);
}

function localDateTime(): string {
  return toLocalDateTime(new Date().toISOString());
}

function toLocalDateTime(value: string): string {
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 16);
}
