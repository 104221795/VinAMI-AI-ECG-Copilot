"use client";

import { Button, ConfirmationDialog } from "@vinami/ui";
import { useForm } from "react-hook-form";
import type {
  ObservationState,
  TriageAssessmentView,
} from "@web/entities/clinical-documentation/model";

const states: Array<{ value: ObservationState; label: string }> = [
  { value: "present", label: "Present" },
  { value: "absent", label: "Absent" },
  { value: "unknown", label: "Unknown" },
  { value: "not_assessed", label: "Not assessed" },
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
          <span>Chief complaint</span>
          <textarea rows={2} {...register("chiefComplaint")} />
        </label>
        <label className="vm-input-field vm-form-span-2">
          <span>Patient-reported symptom description</span>
          <textarea rows={3} {...register("symptomDescription")} />
        </label>
        <label className="vm-input-field">
          <span>Symptom onset status</span>
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
              <span>Reported onset time</span>
              <input
                type="datetime-local"
                required
                {...register("onsetAt", { required: true })}
              />
            </label>
            <label className="vm-input-field">
              <span>Time precision</span>
              <select {...register("onsetPrecision")}>
                <option value="exact">Exact</option>
                <option value="approximate">Approximate</option>
                <option value="date_only">Date only</option>
                <option value="unknown">Unknown precision</option>
              </select>
            </label>
          </>
        )}
      </div>
      <fieldset className="vm-observation-fieldset">
        <legend>Associated symptom documentation</legend>
        <ObservationSelect
          label="Dyspnoea"
          registration={register("dyspnoea")}
        />
        <ObservationSelect label="Nausea" registration={register("nausea")} />
      </fieldset>
      <fieldset className="vm-observation-fieldset">
        <legend>Cardiovascular history documentation</legend>
        <ObservationSelect
          label="Smoking history"
          registration={register("smokingHistory")}
        />
        <ObservationSelect
          label="Diabetes history"
          registration={register("diabetesHistory")}
        />
      </fieldset>
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
                  : "Review entry"}
            </Button>
          }
          title={
            correcting ? "Confirm triage correction" : "Confirm triage entry"
          }
          description={
            correcting
              ? "A new append-only revision will be recorded. The prior entry remains in history."
              : "Record these factual observations in the clinical case?"
          }
          confirmLabel={correcting ? "Record correction" : "Record triage"}
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
