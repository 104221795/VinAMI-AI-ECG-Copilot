import type { VinamiApiClient } from "@vinami/api-client";
import type {
  ECGAnalysisView,
  ECGStudyView,
  ECGWorkspaceView,
} from "@web/entities/ecg/model";
import { parseContract } from "@web/shared/api/parse";
import {
  ecgWaveformSchema,
  ecgWorkspaceSchema,
} from "@web/shared/validation/contracts";

export async function loadECGWorkspaceWith(
  api: VinamiApiClient,
  caseId: string,
): Promise<ECGWorkspaceView> {
  const workspace = parseContract(
    ecgWorkspaceSchema,
    await api.getECGWorkspace(caseId),
  );
  const waveform =
    workspace.current_study?.waveform_available === true
      ? parseContract(
          ecgWaveformSchema,
          await api.getECGWaveform(workspace.current_study.study_id),
        )
      : null;
  return {
    caseId: workspace.clinical_case_id,
    studies: workspace.studies.map(studyView),
    currentStudy: workspace.current_study
      ? studyView(workspace.current_study)
      : null,
    quality: workspace.quality
      ? {
          status: workspace.quality.status,
          reasonCodes: workspace.quality.reason_codes,
          affectedLeads: workspace.quality.affected_leads,
          assessedAt: workspace.quality.assessed_at,
          engineVersion: workspace.quality.quality_engine_version,
          suppressScoreEmphasis: workspace.quality.suppress_score_emphasis,
        }
      : null,
    analyses: workspace.analyses.map(analysisView),
    interpretations: workspace.interpretations.map((item) => ({
      interpretationId: item.interpretation_id,
      status: item.interpretation_status,
      summary: item.structured_interpretation,
      actorRole: item.actor_role,
      recordedAt: item.recorded_at,
      recordVersion: item.record_version,
    })),
    comparisons: workspace.comparisons.map((item) => ({
      comparisonId: item.comparison_id,
      baselineStudyId: item.baseline_study_id,
      currentStudyId: item.current_study_id,
      status: item.status,
      comparabilityStatus: item.comparability_status,
    })),
    reminders: workspace.reminders.map((item) => ({
      reminderId: item.reminder_id,
      sourceStudyId: item.source_study_id,
      reason: item.reason,
      dueAt: item.due_at,
      status: item.status,
    })),
    waveform: waveform
      ? {
          studyReference: waveform.study_reference,
          samplingRateHz: waveform.sampling_rate_hz,
          amplitudeUnit: waveform.amplitude_unit,
          leads: waveform.leads,
        }
      : null,
    safetyNotice: workspace.safety_notice,
  };
}

function studyView(
  value: (typeof ecgWorkspaceSchema._output.studies)[number],
): ECGStudyView {
  return {
    studyId: value.study_id,
    studyReference: value.study_reference,
    sourceType: value.source_type,
    acquisitionAt: value.acquisition_at,
    qualityStatus: value.quality_status,
    samplingRateHz: value.sampling_rate_hz,
    durationSeconds: value.duration_seconds,
    amplitudeUnit: value.amplitude_unit,
    leadConfiguration: value.lead_configuration,
    waveformAvailable: value.waveform_available,
    preprocessingVersion: value.preprocessing_version,
  };
}

function analysisView(
  value: (typeof ecgWorkspaceSchema._output.analyses)[number],
): ECGAnalysisView {
  return {
    analysisId: value.analysis_id,
    studyId: value.ecg_study_id,
    status: value.status,
    qualityStatus: value.quality_status,
    modelName: value.model_name,
    modelVersion: value.model_version,
    providerName: value.provider_name,
    synthetic: value.synthetic,
    completedAt: value.completed_at,
    findings: value.findings.map((item) => ({
      code: item.finding_code,
      label: item.display_label,
      score: item.model_score,
      threshold: item.threshold,
      thresholdMet: item.threshold_met,
      rank: item.rank,
      status: item.finding_status,
    })),
    warnings: value.warnings,
    explanationStatus: value.explanation_status,
    safetyNotice: value.safety_notice,
  };
}
