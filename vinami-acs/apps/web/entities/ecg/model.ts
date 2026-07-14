export interface ECGStudyView {
  studyId: string;
  studyReference: string;
  sourceType: string;
  acquisitionAt: string;
  qualityStatus: string;
  samplingRateHz: number | null;
  durationSeconds: number | null;
  amplitudeUnit: string | null;
  leadConfiguration: string;
  waveformAvailable: boolean;
  preprocessingVersion: string | null;
}

export interface ECGFindingView {
  code: string;
  label: string;
  score: number;
  threshold: number | null;
  thresholdMet: boolean | null;
  rank: number;
  status: string;
}

export interface ECGAnalysisView {
  analysisId: string;
  studyId: string;
  status: string;
  qualityStatus: string;
  modelName: string;
  modelVersion: string;
  providerName: string;
  synthetic: boolean;
  completedAt: string | null;
  findings: ECGFindingView[];
  warnings: string[];
  explanationStatus: string;
  safetyNotice: string;
}

export interface ECGQualityView {
  status: string;
  reasonCodes: string[];
  affectedLeads: string[];
  assessedAt: string;
  engineVersion: string;
  suppressScoreEmphasis: boolean;
}

export interface ECGWaveformView {
  studyReference: string;
  samplingRateHz: number;
  amplitudeUnit: string;
  leads: Array<{ name: string; samples: number[] }>;
}

export interface ECGWorkspaceView {
  caseId: string;
  studies: ECGStudyView[];
  currentStudy: ECGStudyView | null;
  quality: ECGQualityView | null;
  analyses: ECGAnalysisView[];
  interpretations: Array<{
    interpretationId: string;
    status: string;
    summary: string;
    actorRole: string;
    recordedAt: string;
    recordVersion: number;
  }>;
  comparisons: Array<{
    comparisonId: string;
    baselineStudyId: string;
    currentStudyId: string;
    status: string;
    comparabilityStatus: string;
  }>;
  reminders: Array<{
    reminderId: string;
    sourceStudyId: string;
    reason: string;
    dueAt: string;
    status: string;
  }>;
  waveform: ECGWaveformView | null;
  safetyNotice: string;
}
