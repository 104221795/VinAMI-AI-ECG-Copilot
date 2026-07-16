import type { VinamiApiClient } from "@vinami/api-client";
import type {
  ECGAnalysisView,
  ECGStudyView,
  ECGWorkspaceView,
} from "@web/entities/ecg/model";
import { parseContract } from "@web/shared/api/parse";
import {
  ecgConnectorSchema,
  ecgWaveformSchema,
  ecgWorkspaceSchema,
} from "@web/shared/validation/contracts";

export async function loadECGWorkspaceWith(
  api: VinamiApiClient,
  caseId: string,
): Promise<ECGWorkspaceView> {
  const [workspace, connectors] = await Promise.all([
    api
      .getECGWorkspace(caseId)
      .then((result) => parseContract(ecgWorkspaceSchema, result)),
    api
      .getECGConnectors()
      .then((result) =>
        result.map((item) => parseContract(ecgConnectorSchema, item)),
      ),
  ]);
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
      studyId: item.ecg_study_id,
      status: item.interpretation_status,
      summary: item.structured_interpretation,
      actorRole: item.actor_role,
      recordedAt: item.recorded_at,
      recordVersion: item.record_version,
    })),
    ingestionJobs: workspace.ingestion_jobs.map((item) => ({
      jobId: item.ingestion_job_id,
      sourceType: displayEnum(item.source_type),
      connectorId: item.source_connector_id,
      externalReference: item.external_reference,
      status: displayEnum(item.status),
      requestedAt: item.requested_at,
      completedAt: item.completed_at,
      parser: item.parser_name,
      parserVersion: item.parser_version,
      warnings: item.warnings,
      failureCategory: item.failure_category,
      failureDetail: item.failure_detail_safe,
      retryCount: item.retry_count,
      correlationId: item.correlation_id,
      recordVersion: item.record_version,
    })),
    comparisons: workspace.comparisons.map((item) => ({
      comparisonId: item.comparison_id,
      baselineStudyId: item.baseline_study_id,
      currentStudyId: item.current_study_id,
      status: item.status,
      comparabilityStatus: item.comparability_status,
      comparabilityReasons: item.comparability_reasons,
      leadComparisons: item.lead_comparisons.map((lead) => ({
        leadName: lead.lead_name,
        waveformSimilarity: lead.waveform_similarity,
        normalizedDifference: lead.normalized_difference,
        amplitudeScaleChange: lead.amplitude_scale_change,
        baselineShiftIndicator: lead.baseline_shift_indicator,
        missingDataPercentage: lead.missing_data_percentage,
        qualityDifference: lead.quality_difference,
        sampleAlignmentStatus: lead.sample_alignment_status,
      })),
      technicalChangeIndicators: item.technical_change_indicators,
      scoreEvolution: item.model_score_deltas.map((score) => ({
        findingCode: score.finding_code,
        previousScore: score.previous_score,
        currentScore: score.current_score,
        absoluteDelta: score.absolute_delta,
        compatibilityStatus: score.compatibility_status,
      })),
      scoreCompatibility: item.model_score_compatibility,
      policyVersion: item.comparison_policy_version,
      recordVersion: item.record_version,
      safetyNotice: item.safety_notice,
    })),
    comparisonReviews: workspace.comparison_reviews.map((item) => ({
      reviewId: item.review_id,
      comparisonId: item.comparison_id,
      reviewStatus: item.review_status,
      interpretation: item.interpretation,
      actorRole: item.actor_role,
      recordedAt: item.recorded_at,
      recordVersion: item.record_version,
    })),
    reminders: workspace.reminders.map((item) => ({
      reminderId: item.reminder_id,
      sourceStudyId: item.source_study_id,
      reason: item.reason,
      dueAt: item.due_at,
      status: item.status,
      origin: item.origin,
      requestedByRole: item.requested_by_actor_role,
      acknowledgedAt: item.acknowledged_at,
      completedStudyId: item.completed_study_id,
      completedAt: item.completed_at,
      cancellationReason: item.cancellation_reason,
      recordVersion: item.record_version,
    })),
    capabilities: workspace.capabilities,
    connectors: connectors.map((item) => ({
      connectorId: item.connector_id,
      displayName: item.display_name,
      sourceType: displayEnum(item.source_type),
      available: item.available,
      capabilities: item.capabilities,
      detail: item.detail,
      connectorType: displayEnum(item.connector_type),
      profile: item.profile,
      version: item.version,
    })),
    dataFreshness: workspace.data_freshness,
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

function displayEnum(value: string): string {
  return /^[a-z][a-z0-9_]*$/i.test(value) ? value : "Unknown";
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
