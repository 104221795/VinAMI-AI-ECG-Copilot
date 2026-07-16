import { z } from "zod";

const uuid = z.string().uuid();
const timestamp = z.string().datetime({ offset: true });

export const identitySchema = z.object({
  actor_id: uuid,
  subject_id: z.string().min(1),
  display_name: z.string().min(1),
  roles: z.array(z.string()),
  permissions: z.array(z.string()),
  organization: z.string().nullable(),
  location_scope: z.array(z.string()),
  authentication_method: z.string(),
  identity_provider: z.string(),
  identity_mode: z.string(),
  development_only: z.boolean(),
  expires_at: timestamp,
});

export const patientSchema = z.object({
  patient_id: uuid,
  patient_reference: z.string().min(1),
  reference_system: z.string().min(1),
  safe_demographic_summary: z.object({
    age_band: z.string().nullable().optional(),
    sex_at_birth: z.string().nullable().optional(),
  }),
  aggregate_version: z.number().int().positive(),
  created_at: timestamp,
  updated_at: timestamp,
});

export const encounterSchema = z.object({
  encounter_id: uuid,
  patient_id: uuid,
  location: z.string().min(1),
  status: z.string().min(1),
  arrival_at: timestamp,
  aggregate_version: z.number().int().positive(),
  created_at: timestamp,
  updated_at: timestamp,
});

export const caseListItemSchema = z.object({
  case_id: uuid,
  encounter_id: uuid,
  priority: z.string().min(1),
  status: z.string().min(1),
  location: z.string().min(1),
  opened_at: timestamp,
  updated_at: timestamp,
  aggregate_version: z.number().int().positive(),
});

export const casePageSchema = z.object({
  items: z.array(caseListItemSchema),
  page: z.number().int().positive(),
  page_size: z.number().int().positive(),
  total: z.number().int().nonnegative(),
});

export const caseDetailSchema = caseListItemSchema
  .omit({ location: true })
  .extend({
    opening_reason: z.string().min(1),
  });

export const timelineSchema = z.array(
  z.object({
    timeline_event_id: uuid,
    clinical_case_id: uuid,
    event_type: z.string().min(1),
    title: z.string().min(1),
    occurred_at: timestamp,
    recorded_at: timestamp,
    source: z.string().min(1),
    actor_id: z.string().nullable(),
    correlation_id: z.string().min(1),
    causation_id: z.string().nullable(),
  }),
);

export const auditSchema = z.array(
  z.object({
    audit_id: uuid,
    actor_id: z.string().nullable(),
    actor_role: z.string().nullable(),
    actor_roles: z.array(z.string()),
    action: z.string(),
    resource_type: z.string(),
    resource_id: uuid,
    outcome: z.string(),
    prior_version: z.number().int().nullable(),
    resulting_version: z.number().int().nullable(),
    request_source: z.string(),
    recorded_at: timestamp,
    reason: z.string().nullable(),
    correlation_id: z.string(),
    causation_id: z.string().nullable(),
    identity_subject: z.string().nullable(),
    applied_permission: z.string().nullable(),
    identity_provider: z.string().nullable(),
    authentication_method: z.string().nullable(),
    session_reference: z.string().nullable(),
  }),
);

export const timelineHistoryPageSchema = z.object({
  items: z.array(
    z.object({
      timeline_event_id: uuid,
      clinical_case_id: uuid,
      event_type: z.string().min(1),
      title: z.string().min(1),
      occurred_at: timestamp,
      recorded_at: timestamp,
      source: z.string().min(1),
      actor_id: uuid.nullable(),
      correlation_id: uuid,
      causation_id: uuid.nullable(),
      source_record_id: uuid.nullable(),
      source_record_version: z.number().int().nullable(),
      correction_status: z.string().min(1),
      supersedes_timeline_event_id: uuid.nullable(),
      revokes_timeline_event_id: uuid.nullable(),
      data_classification: z.string().min(1),
    }),
  ),
  page: z.number().int().positive(),
  page_size: z.number().int().positive(),
  total: z.number().int().nonnegative(),
});

export const auditHistoryPageSchema = z.object({
  items: z.array(
    z.object({
      audit_id: uuid,
      actor_id: uuid.nullable(),
      actor_role: z.string().nullable(),
      identity_subject: z.string().nullable(),
      actor_roles: z.array(z.string()),
      applied_permission: z.string().nullable(),
      identity_provider: z.string().nullable(),
      authentication_method: z.string().nullable(),
      session_reference: z.string().nullable(),
      action: z.string(),
      resource_type: z.string(),
      resource_id: uuid,
      request_source: z.string(),
      correlation_id: uuid,
      causation_id: uuid.nullable(),
      prior_version: z.number().int().nullable(),
      resulting_version: z.number().int().nullable(),
      outcome: z.string(),
      reason: z.string().nullable(),
      recorded_at: timestamp,
      idempotency_key: z.string().nullable(),
      authorization_result: z.string().nullable(),
      correction_status: z.string(),
      source_record_version: z.number().int().nullable(),
    }),
  ),
  page: z.number().int().positive(),
  page_size: z.number().int().positive(),
  total: z.number().int().nonnegative(),
});

export const outcomeResponseSchema = z.object({
  outcome_id: uuid,
  clinical_case_id: uuid,
  outcome_type: z.string(),
  outcome_timestamp: timestamp,
  final_conclusion: z.string(),
  disposition: z.string().nullable(),
  destination: z.string().nullable(),
  cath_lab_review_outcome: z.string().nullable(),
  intervention_reference: z.string().nullable(),
  complications: z.string().nullable(),
  follow_up_status: z.string().nullable(),
  data_completeness: z.string(),
  source: z.string(),
  uncertainty: z.string().nullable(),
  unavailable_reason: z.string().nullable(),
  recorded_at: timestamp,
  recorded_by: uuid,
  actor_role: z.string(),
  revision_number: z.number().int().positive(),
  record_version: z.number().int().positive(),
  supersedes_outcome_id: uuid.nullable(),
  correction_reason: z.string().nullable(),
  correlation_id: uuid.nullable(),
  causation_id: uuid.nullable(),
});

export const outcomeHistorySchema = z.object({
  current: outcomeResponseSchema.nullable(),
  revisions: z.array(outcomeResponseSchema),
  safety_notice: z.string(),
});

export const modelProvenanceSchema = z.array(
  z.object({
    analysis_id: uuid,
    study_id: uuid,
    provider_name: z.string(),
    provider_version: z.string(),
    model_name: z.string(),
    model_version: z.string(),
    model_checksum: z.string().nullable(),
    threshold_version: z.string().nullable(),
    preprocessing_version: z.string(),
    label_mapping_version: z.string(),
    executed_at: timestamp.nullable(),
    input_quality: z.string(),
    input_artifact_id: uuid,
    input_artifact_checksum: z.string(),
    explanation_artifact_id: uuid.nullable(),
    explanation_status: z.string(),
    synthetic: z.boolean(),
    status: z.string(),
    warnings: z.array(z.string()),
    record_version: z.number().int().positive(),
    safety_notice: z.string(),
  }),
);

export const researchExportSchema = z.object({
  export_id: uuid,
  status: z.string(),
  schema_version: z.string(),
  requested_by: uuid,
  requested_by_role: z.string(),
  requested_at: timestamp,
  completed_at: timestamp.nullable(),
  case_ids: z.array(uuid),
  filters: z.record(z.string(), z.unknown()),
  row_count: z.number().int().nonnegative(),
  pseudonymization_method: z.string(),
  checksum_sha256: z.string(),
  content_json: z.record(z.string(), z.unknown()),
  content_csv: z.string(),
  correlation_id: uuid,
  metadata: z.record(z.string(), z.unknown()),
  safety_notice: z.string(),
});

export const healthSchema = z
  .object({
    status: z.string(),
    service: z.string().optional(),
    dependency: z.string().optional(),
    revision: z.string().optional(),
    identity: z
      .object({
        mode: z.string(),
        status: z.string(),
        provider: z.string(),
        development_only: z.boolean(),
      })
      .optional(),
  })
  .passthrough();

const observationStateSchema = z.enum([
  "present",
  "absent",
  "unknown",
  "not_assessed",
]);

const structuredObservationSchema = z.object({
  name: z.string().min(1),
  state: observationStateSchema,
  note: z.string().nullable().optional(),
});

export const triageAssessmentSchema = z.object({
  assessment_id: uuid,
  clinical_case_id: uuid,
  revision_number: z.number().int().positive(),
  status: z.string().min(1),
  source: z.string().min(1),
  recorded_by_actor_id: uuid,
  recorded_by_actor_role: z.string().min(1),
  occurred_at: timestamp,
  recorded_at: timestamp,
  correlation_id: uuid,
  causation_id: uuid.nullable(),
  record_version: z.number().int().positive(),
  chief_complaint: z.string().nullable(),
  symptom_onset_state: observationStateSchema,
  symptom_onset_at: timestamp.nullable(),
  symptom_onset_precision: z.string().nullable(),
  symptom_description: z.string().nullable(),
  symptom_location: z.string().nullable(),
  symptom_radiation: z.string().nullable(),
  symptom_duration: z.string().nullable(),
  symptom_pattern: z.string().nullable(),
  aggravating_factors: z.string().nullable(),
  relieving_factors: z.string().nullable(),
  relevant_history_summary: z.string().nullable(),
  current_medication_summary: z.string().nullable(),
  allergy_summary: z.string().nullable(),
  clinical_note: z.string().nullable(),
  associated_symptoms: z.array(structuredObservationSchema),
  cardiovascular_risk_factors: z.array(structuredObservationSchema),
  corrects_assessment_id: uuid.nullable(),
  correction_reason: z.string().nullable(),
});

export const vitalObservationSetSchema = z.object({
  vital_set_id: uuid,
  clinical_case_id: uuid,
  encounter_id: uuid,
  sequence_number: z.number().int().positive(),
  revision_number: z.number().int().positive(),
  source: z.string().min(1),
  device_reference: z.string().nullable(),
  recorded_by_actor_id: uuid,
  recorded_by_actor_role: z.string().min(1),
  observed_at: timestamp,
  recorded_at: timestamp,
  correlation_id: uuid,
  causation_id: uuid.nullable(),
  record_version: z.number().int().positive(),
  measurements: z.array(
    z.object({
      kind: z.string().min(1),
      value: z.number().finite(),
      unit: z.string().min(1),
      source: z.string().min(1),
      observed_at: timestamp,
      quality_status: z.string().min(1),
    }),
  ),
  supplemental_oxygen_state: observationStateSchema,
  oxygen_delivery_method: z.string().nullable(),
  level_of_consciousness: z.string().nullable(),
  observation_note: z.string().nullable(),
  corrects_vital_set_id: uuid.nullable(),
  correction_reason: z.string().nullable(),
});

export const triageHistorySchema = z.object({
  items: z.array(triageAssessmentSchema),
  total: z.number().int().nonnegative(),
});

export const vitalHistorySchema = z.object({
  items: z.array(vitalObservationSetSchema),
  total: z.number().int().nonnegative(),
});

export const triageVitalsSummarySchema = z.object({
  current_triage: triageAssessmentSchema.nullable(),
  latest_vitals: vitalObservationSetSchema.nullable(),
  recent_vitals: z.array(vitalObservationSetSchema),
  missing_documentation: z.array(
    z.object({ identifier: z.string().min(1), description: z.string().min(1) }),
  ),
  completeness_policy_version: z.string().min(1),
  data_freshness_at: timestamp,
  case_version: z.number().int().positive(),
});

export const ecgStudySchema = z.object({
  study_id: uuid,
  clinical_case_id: uuid,
  encounter_id: uuid,
  study_reference: z.string().min(1),
  source_type: z.string().min(1),
  source_system: z.string().min(1),
  acquisition_at: timestamp,
  ingestion_at: timestamp,
  study_status: z.string().min(1),
  lead_configuration: z.string().min(1),
  sampling_rate_hz: z.number().positive().nullable(),
  duration_seconds: z.number().positive().nullable(),
  amplitude_unit: z.string().nullable(),
  source_format: z.string().min(1),
  artifact_checksum: z.string().min(1),
  parser_version: z.string().min(1),
  preprocessing_version: z.string().nullable(),
  quality_status: z.string().min(1),
  aggregate_version: z.number().int().positive(),
  waveform_available: z.boolean(),
});

export const ecgFindingSchema = z.object({
  finding_code: z.string().min(1),
  display_label: z.string().min(1),
  model_score: z.number().min(0).max(1),
  threshold: z.number().min(0).max(1).nullable(),
  threshold_met: z.boolean().nullable(),
  rank: z.number().int().positive(),
  finding_status: z.string().min(1),
  explanation_reference: z.string().nullable(),
});

export const ecgAnalysisSchema = z.object({
  analysis_id: uuid,
  ecg_study_id: uuid,
  provider_name: z.string().min(1),
  provider_version: z.string().min(1),
  model_name: z.string().min(1),
  model_version: z.string().min(1),
  model_checksum: z.string().nullable(),
  preprocessing_version: z.string().min(1),
  threshold_version: z.string().nullable(),
  status: z.string().min(1),
  quality_status: z.string().min(1),
  requested_at: timestamp,
  completed_at: timestamp.nullable(),
  inference_duration_ms: z.number().int().nonnegative().nullable(),
  findings: z.array(ecgFindingSchema),
  warnings: z.array(z.string()),
  explanation_status: z.string().min(1),
  explanation_artifact_id: uuid.nullable(),
  failure_category: z.string().nullable(),
  failure_detail_safe: z.string().nullable(),
  correlation_id: uuid,
  record_version: z.number().int().positive(),
  synthetic: z.boolean(),
  safety_notice: z.string().min(1),
});

export const ecgQualitySchema = z.object({
  status: z.string().min(1),
  reason_codes: z.array(z.string()),
  affected_leads: z.array(z.string()),
  parser_warnings: z.array(z.string()),
  preprocessing_warnings: z.array(z.string()),
  quality_engine_version: z.string().min(1),
  assessed_at: timestamp,
  suppress_score_emphasis: z.boolean(),
});

const ecgInterpretationSchema = z
  .object({
    interpretation_id: uuid,
    ecg_study_id: uuid,
    analysis_id: uuid.nullable(),
    actor_role: z.string().min(1),
    interpretation_status: z.string().min(1),
    structured_interpretation: z.string().min(1),
    agreement_status: z.string().min(1),
    quality_disposition: z.string().min(1),
    repeat_ecg_requested: z.boolean(),
    occurred_at: timestamp,
    recorded_at: timestamp,
    record_version: z.number().int().positive(),
    revision_number: z.number().int().positive(),
  })
  .passthrough();

export const ecgWorkspaceSchema = z.object({
  clinical_case_id: uuid,
  studies: z.array(ecgStudySchema),
  current_study: ecgStudySchema.nullable(),
  quality: ecgQualitySchema.nullable(),
  analyses: z.array(ecgAnalysisSchema),
  interpretations: z.array(ecgInterpretationSchema),
  ingestion_jobs: z.array(
    z.object({
      ingestion_job_id: uuid,
      source_type: z.string(),
      source_connector_id: z.string().nullable(),
      external_reference: z.string().nullable(),
      status: z.string(),
      requested_at: timestamp,
      completed_at: timestamp.nullable(),
      parser_name: z.string().nullable(),
      parser_version: z.string().nullable(),
      warnings: z.array(z.string()),
      failure_category: z.string().nullable(),
      failure_detail_safe: z.string().nullable(),
      retry_count: z.number().int().nonnegative(),
      correlation_id: uuid,
      record_version: z.number().int().positive(),
    }),
  ),
  comparisons: z.array(
    z
      .object({
        comparison_id: uuid,
        baseline_study_id: uuid,
        current_study_id: uuid,
        status: z.string().min(1),
        comparability_status: z.string().min(1),
        comparability_reasons: z.array(z.string()),
        lead_comparisons: z.array(
          z.object({
            lead_name: z.string(),
            waveform_similarity: z.number(),
            normalized_difference: z.number(),
            amplitude_scale_change: z.number(),
            baseline_shift_indicator: z.number(),
            missing_data_percentage: z.number(),
            quality_difference: z.string(),
            sample_alignment_status: z.string(),
          }),
        ),
        technical_change_indicators: z.array(z.string()),
        model_score_deltas: z.array(
          z.object({
            finding_code: z.string(),
            previous_score: z.number(),
            current_score: z.number(),
            absolute_delta: z.number(),
            compatibility_status: z.string(),
          }),
        ),
        model_score_compatibility: z.string(),
        comparison_policy_version: z.string(),
        record_version: z.number().int().positive(),
        safety_notice: z.string().min(1),
      })
      .passthrough(),
  ),
  comparison_reviews: z.array(
    z.object({
      review_id: uuid,
      comparison_id: uuid,
      actor_role: z.string(),
      review_status: z.string(),
      interpretation: z.string(),
      recorded_at: timestamp,
      record_version: z.number().int().positive(),
    }),
  ),
  reminders: z.array(
    z
      .object({
        reminder_id: uuid,
        source_study_id: uuid,
        reason: z.string().min(1),
        due_at: timestamp,
        status: z.string().min(1),
        origin: z.string(),
        requested_by_actor_role: z.string(),
        acknowledged_at: timestamp.nullable(),
        completed_study_id: uuid.nullable(),
        completed_at: timestamp.nullable(),
        cancellation_reason: z.string().nullable(),
        record_version: z.number().int().positive(),
      })
      .passthrough(),
  ),
  capabilities: z.record(z.string(), z.boolean()),
  data_freshness: timestamp,
  safety_notice: z.string().min(1),
});

export const ecgWaveformSchema = z.object({
  schema_version: z.string().min(1),
  study_reference: z.string().min(1),
  sampling_rate_hz: z.number().positive(),
  amplitude_unit: z.string().min(1),
  source_amplitude_unit: z.string().min(1),
  conversion_method: z.string().nullable(),
  preprocessing_version: z.string().min(1),
  lead_order: z.array(z.string().min(1)),
  leads: z.array(
    z.object({
      name: z.string().min(1),
      samples: z.array(z.number().finite()).min(1),
    }),
  ),
});

export const ecgConnectorSchema = z.object({
  connector_id: z.string(),
  display_name: z.string(),
  source_type: z.string(),
  available: z.boolean(),
  capabilities: z.array(z.string()),
  detail: z.string(),
  connector_type: z.string(),
  profile: z.string().nullable(),
  version: z.string().nullable(),
});
