export interface OutcomeView {
  outcomeId: string;
  outcomeType: string;
  outcomeTimestamp: string;
  finalConclusion: string;
  disposition: string | null;
  destination: string | null;
  dataCompleteness: string;
  source: string;
  uncertainty: string | null;
  unavailableReason: string | null;
  recordedAt: string;
  recordedBy: string;
  actorRole: string;
  revisionNumber: number;
  recordVersion: number;
  supersedesOutcomeId: string | null;
  correctionReason: string | null;
}

export interface OutcomeHistoryView {
  current: OutcomeView | null;
  revisions: OutcomeView[];
  safetyNotice: string;
}

export interface ModelProvenanceView {
  analysisId: string;
  studyId: string;
  providerName: string;
  providerVersion: string;
  modelName: string;
  modelVersion: string;
  modelChecksum: string | null;
  thresholdVersion: string | null;
  executedAt: string | null;
  inputQuality: string;
  explanationStatus: string;
  synthetic: boolean;
  status: string;
  warnings: string[];
  recordVersion: number;
  safetyNotice: string;
}

export interface ResearchExportView {
  exportId: string;
  status: string;
  schemaVersion: string;
  rowCount: number;
  checksumSha256: string;
  pseudonymizationMethod: string;
  contentCsv: string;
  requestedAt: string;
  safetyNotice: string;
}
