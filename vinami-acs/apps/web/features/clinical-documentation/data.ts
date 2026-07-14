import type { VinamiApiClient } from "@vinami/api-client";
import type {
  ClinicalDocumentationView,
  TriageAssessmentView,
  VitalObservationSetView,
} from "@web/entities/clinical-documentation/model";
import { parseContract } from "@web/shared/api/parse";
import {
  triageHistorySchema,
  triageVitalsSummarySchema,
  vitalHistorySchema,
} from "@web/shared/validation/contracts";

export async function loadClinicalDocumentationWith(
  api: VinamiApiClient,
  caseId: string,
): Promise<ClinicalDocumentationView> {
  const [summaryValue, triageHistoryValue, vitalHistoryValue] =
    await Promise.all([
      api.getTriageVitalsSummary(caseId),
      api.getTriageHistory(caseId),
      api.getVitalHistory(caseId),
    ]);
  const summary = parseContract(triageVitalsSummarySchema, summaryValue);
  const triageHistory = parseContract(triageHistorySchema, triageHistoryValue);
  const vitalHistory = parseContract(vitalHistorySchema, vitalHistoryValue);
  return {
    currentTriage: summary.current_triage
      ? triageView(summary.current_triage)
      : null,
    triageHistory: triageHistory.items.map(triageView),
    latestVitals: summary.latest_vitals
      ? vitalView(summary.latest_vitals)
      : null,
    vitalHistory: vitalHistory.items.map(vitalView),
    missingDocumentation: summary.missing_documentation,
    completenessPolicyVersion: summary.completeness_policy_version,
    dataFreshnessAt: summary.data_freshness_at,
    caseVersion: summary.case_version,
  };
}

function triageView(
  value: (typeof triageHistorySchema._output.items)[number],
): TriageAssessmentView {
  return {
    assessmentId: value.assessment_id,
    revisionNumber: value.revision_number,
    status: value.status,
    source: value.source,
    recordedBy: value.recorded_by_actor_role,
    occurredAt: value.occurred_at,
    recordedAt: value.recorded_at,
    recordVersion: value.record_version,
    chiefComplaint: value.chief_complaint,
    symptomOnsetState: value.symptom_onset_state,
    symptomOnsetAt: value.symptom_onset_at,
    symptomOnsetPrecision: value.symptom_onset_precision,
    symptomDescription: value.symptom_description,
    associatedSymptoms: value.associated_symptoms.map((item) => ({
      name: item.name,
      state: item.state,
      note: item.note ?? null,
    })),
    riskFactors: value.cardiovascular_risk_factors.map((item) => ({
      name: item.name,
      state: item.state,
      note: item.note ?? null,
    })),
    correctsAssessmentId: value.corrects_assessment_id,
    correctionReason: value.correction_reason,
  };
}

function vitalView(
  value: (typeof vitalHistorySchema._output.items)[number],
): VitalObservationSetView {
  return {
    vitalSetId: value.vital_set_id,
    sequenceNumber: value.sequence_number,
    revisionNumber: value.revision_number,
    source: value.source,
    recordedBy: value.recorded_by_actor_role,
    observedAt: value.observed_at,
    recordedAt: value.recorded_at,
    recordVersion: value.record_version,
    measurements: value.measurements.map((item) => ({
      kind: item.kind,
      value: item.value,
      unit: item.unit,
      source: item.source,
      observedAt: item.observed_at,
      qualityStatus: item.quality_status,
    })),
    supplementalOxygenState: value.supplemental_oxygen_state,
    correctsVitalSetId: value.corrects_vital_set_id,
    correctionReason: value.correction_reason,
  };
}
