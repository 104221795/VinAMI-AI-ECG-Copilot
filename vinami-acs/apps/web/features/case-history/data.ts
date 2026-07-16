import type { VinamiApiClient } from "@vinami/api-client";
import { parseContract } from "@web/shared/api/parse";
import {
  modelProvenanceSchema,
  outcomeHistorySchema,
  outcomeResponseSchema,
  researchExportSchema,
} from "@web/shared/validation/contracts";
import type {
  ModelProvenanceView,
  OutcomeHistoryView,
  OutcomeView,
  ResearchExportView,
} from "./model";

export async function loadOutcomeHistoryWith(
  api: VinamiApiClient,
  caseId: string,
): Promise<OutcomeHistoryView> {
  const value = parseContract(
    outcomeHistorySchema,
    await api.getOutcomeHistory(caseId),
  );
  return {
    current: value.current ? mapOutcome(value.current) : null,
    revisions: value.revisions.map(mapOutcome),
    safetyNotice: value.safety_notice,
  };
}

export async function loadModelProvenanceWith(
  api: VinamiApiClient,
  caseId: string,
): Promise<ModelProvenanceView[]> {
  return parseContract(
    modelProvenanceSchema,
    await api.getModelProvenance(caseId),
  ).map((item) => ({
    analysisId: item.analysis_id,
    studyId: item.study_id,
    providerName: item.provider_name,
    providerVersion: item.provider_version,
    modelName: item.model_name,
    modelVersion: item.model_version,
    modelChecksum: item.model_checksum,
    thresholdVersion: item.threshold_version,
    executedAt: item.executed_at,
    inputQuality: item.input_quality,
    explanationStatus: item.explanation_status,
    synthetic: item.synthetic,
    status: item.status,
    warnings: item.warnings,
    recordVersion: item.record_version,
    safetyNotice: item.safety_notice,
  }));
}

export async function recordOutcomeWith(
  api: VinamiApiClient,
  caseId: string,
  body: Record<string, unknown>,
  idempotencyKey: string,
): Promise<OutcomeView> {
  return mapOutcome(
    parseContract(
      outcomeResponseSchema,
      await api.recordOutcome(caseId, body, idempotencyKey),
    ),
  );
}

export async function correctOutcomeWith(
  api: VinamiApiClient,
  caseId: string,
  outcomeId: string,
  body: Record<string, unknown>,
  idempotencyKey: string,
): Promise<OutcomeView> {
  return mapOutcome(
    parseContract(
      outcomeResponseSchema,
      await api.correctOutcome(caseId, outcomeId, body, idempotencyKey),
    ),
  );
}

export async function requestResearchExportWith(
  api: VinamiApiClient,
  caseId: string,
  idempotencyKey: string,
): Promise<ResearchExportView> {
  const value = parseContract(
    researchExportSchema,
    await api.requestResearchExport([caseId], idempotencyKey),
  );
  return {
    exportId: value.export_id,
    status: value.status,
    schemaVersion: value.schema_version,
    rowCount: value.row_count,
    checksumSha256: value.checksum_sha256,
    pseudonymizationMethod: value.pseudonymization_method,
    contentCsv: value.content_csv,
    requestedAt: value.requested_at,
    safetyNotice: value.safety_notice,
  };
}

function mapOutcome(value: {
  outcome_id: string;
  outcome_type: string;
  outcome_timestamp: string;
  final_conclusion: string;
  disposition: string | null;
  destination: string | null;
  data_completeness: string;
  source: string;
  uncertainty: string | null;
  unavailable_reason: string | null;
  recorded_at: string;
  recorded_by: string;
  actor_role: string;
  revision_number: number;
  record_version: number;
  supersedes_outcome_id: string | null;
  correction_reason: string | null;
}): OutcomeView {
  return {
    outcomeId: value.outcome_id,
    outcomeType: value.outcome_type,
    outcomeTimestamp: value.outcome_timestamp,
    finalConclusion: value.final_conclusion,
    disposition: value.disposition,
    destination: value.destination,
    dataCompleteness: value.data_completeness,
    source: value.source,
    uncertainty: value.uncertainty,
    unavailableReason: value.unavailable_reason,
    recordedAt: value.recorded_at,
    recordedBy: value.recorded_by,
    actorRole: value.actor_role,
    revisionNumber: value.revision_number,
    recordVersion: value.record_version,
    supersedesOutcomeId: value.supersedes_outcome_id,
    correctionReason: value.correction_reason,
  };
}
