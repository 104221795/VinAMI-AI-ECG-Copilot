export type ObservationState =
  "present" | "absent" | "unknown" | "not_assessed";

export interface StructuredObservationView {
  name: string;
  state: ObservationState;
  note: string | null;
}

export interface TriageAssessmentView {
  assessmentId: string;
  revisionNumber: number;
  status: string;
  source: string;
  recordedBy: string;
  occurredAt: string;
  recordedAt: string;
  recordVersion: number;
  chiefComplaint: string | null;
  symptomOnsetState: ObservationState;
  symptomOnsetAt: string | null;
  symptomOnsetPrecision: string | null;
  symptomDescription: string | null;
  associatedSymptoms: StructuredObservationView[];
  riskFactors: StructuredObservationView[];
  correctsAssessmentId: string | null;
  correctionReason: string | null;
}

export interface VitalMeasurementView {
  kind: string;
  value: number;
  unit: string;
  source: string;
  observedAt: string;
  qualityStatus: string;
}

export interface VitalObservationSetView {
  vitalSetId: string;
  sequenceNumber: number;
  revisionNumber: number;
  source: string;
  recordedBy: string;
  observedAt: string;
  recordedAt: string;
  recordVersion: number;
  measurements: VitalMeasurementView[];
  supplementalOxygenState: ObservationState;
  correctsVitalSetId: string | null;
  correctionReason: string | null;
}

export interface ClinicalDocumentationView {
  currentTriage: TriageAssessmentView | null;
  triageHistory: TriageAssessmentView[];
  latestVitals: VitalObservationSetView | null;
  vitalHistory: VitalObservationSetView[];
  missingDocumentation: Array<{ identifier: string; description: string }>;
  completenessPolicyVersion: string;
  dataFreshnessAt: string;
  caseVersion: number;
}
