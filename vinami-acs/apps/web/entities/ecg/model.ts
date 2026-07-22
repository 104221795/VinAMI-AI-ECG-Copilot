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
  explanationArtifactId: string | null;
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
    studyId: string;
    status: string;
    summary: string;
    actorRole: string;
    recordedAt: string;
    recordVersion: number;
  }>;
  ingestionJobs: Array<{
    jobId: string;
    sourceType: string;
    connectorId: string | null;
    externalReference: string | null;
    status: string;
    requestedAt: string;
    completedAt: string | null;
    parser: string | null;
    parserVersion: string | null;
    warnings: string[];
    failureCategory: string | null;
    failureDetail: string | null;
    retryCount: number;
    correlationId: string;
    recordVersion: number;
  }>;
  comparisons: Array<{
    comparisonId: string;
    baselineStudyId: string;
    currentStudyId: string;
    status: string;
    comparabilityStatus: string;
    comparabilityReasons: string[];
    leadComparisons: Array<{
      leadName: string;
      waveformSimilarity: number;
      normalizedDifference: number;
      amplitudeScaleChange: number;
      baselineShiftIndicator: number;
      missingDataPercentage: number;
      qualityDifference: string;
      sampleAlignmentStatus: string;
    }>;
    technicalChangeIndicators: string[];
    signalFeatureDeltas: Array<{
      featureName: string;
      displayLabel: string;
      previousValue: number | null;
      currentValue: number | null;
      absoluteDelta: number | null;
      unit: string | null;
      status: string;
      evidenceScope: string;
    }>;
    rhythmChangeIndicators: string[];
    stTChangeIndicators: string[];
    scoreEvolution: Array<{
      findingCode: string;
      previousScore: number;
      currentScore: number;
      absoluteDelta: number;
      compatibilityStatus: string;
    }>;
    scoreCompatibility: string;
    policyVersion: string;
    reviewRecommendation: string;
    recordVersion: number;
    safetyNotice: string;
  }>;
  comparisonReviews: Array<{
    reviewId: string;
    comparisonId: string;
    reviewStatus: string;
    interpretation: string;
    actorRole: string;
    recordedAt: string;
    recordVersion: number;
  }>;
  reminders: Array<{
    reminderId: string;
    sourceStudyId: string;
    reason: string;
    dueAt: string;
    status: string;
    origin: string;
    requestedByRole: string;
    acknowledgedAt: string | null;
    completedStudyId: string | null;
    completedAt: string | null;
    cancellationReason: string | null;
    recordVersion: number;
  }>;
  capabilities: Record<string, boolean>;
  connectors: Array<{
    connectorId: string;
    displayName: string;
    sourceType: string;
    available: boolean;
    capabilities: string[];
    detail: string;
    connectorType: string;
    profile: string | null;
    version: string | null;
  }>;
  dataFreshness: string;
  waveform: ECGWaveformView | null;
  safetyNotice: string;
  technicalWarnings: string[];
}
