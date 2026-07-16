export interface TroponinResultView {
  result_id: string;
  assay_id: string;
  assay_code: string;
  assay_display_name: string;
  assay_category: string;
  manufacturer: string;
  platform: string;
  assay_version: string;
  analyte: string;
  original_value: string;
  original_unit: string;
  normalized_value: string | null;
  normalized_unit: string | null;
  conversion_status: string;
  conversion_version: string;
  specimen_type: string;
  specimen_collected_at: string;
  resulted_at: string;
  result_status: string;
  reference_limit_value: string | null;
  reference_limit_unit: string | null;
  reference_limit_source: string | null;
  quality_flags: string[];
  source_system: string;
  source_type: string;
  source_result_id: string;
  source_identity: string;
  source_revision: number;
  accession_number: string | null;
  supersedes_result_id: string | null;
  amendment_reason: string | null;
  recorded_by_role: string;
  recorded_at: string;
  correlation_id: string;
  record_version: number;
}

export interface ClinicianTroponinReviewView {
  review_id: string;
  clinical_case_id: string;
  referenced_result_ids: string[];
  actor_id: string;
  actor_role: string;
  review_status: string;
  incompatibility_acknowledged: boolean;
  quality_limitation_acknowledged: boolean;
  repeat_measurement_requested: boolean;
  repeat_measurement_reason: string | null;
  note: string | null;
  occurred_at: string;
  recorded_at: string;
  correlation_id: string;
  supersedes_review_id: string | null;
  correction_reason: string | null;
  record_version: number;
}

export interface RepeatTroponinRequestView {
  request_id: string;
  clinical_case_id: string;
  source_result_id: string;
  requested_by_actor_id: string;
  reason: string;
  requested_at: string;
  status: string;
  acknowledged_by_actor_id: string | null;
  acknowledged_at: string | null;
  completed_result_id: string | null;
  completed_at: string | null;
  cancellation_reason: string | null;
  correlation_id: string;
  record_version: number;
}

export interface TroponinDeltaView {
  baseline_result_id: string;
  current_result_id: string;
  baseline_value: string;
  current_value: string;
  absolute_change: string | null;
  relative_change_percent: string | null;
  normalized_unit: string | null;
  specimen_interval_seconds: number;
  compatibility_status: string;
  incompatibility_reasons: string[];
  calculation_policy_version: string;
  warning: string;
}

export interface TroponinWorkspaceView {
  clinical_case_id: string;
  case_version: number;
  effective_results: TroponinResultView[];
  result_history: TroponinResultView[];
  latest_result: TroponinResultView | null;
  deltas: TroponinDeltaView[];
  import_jobs: Array<Record<string, unknown>>;
  clinician_reviews: ClinicianTroponinReviewView[];
  latest_clinician_review: ClinicianTroponinReviewView | null;
  repeat_measurement_requests: RepeatTroponinRequestView[];
  data_freshness: string | null;
  capabilities: {
    manual_entry: boolean;
    mock_laboratory_import: boolean;
    live_lis: boolean;
    amendment: boolean;
    clinician_review: boolean;
    repeat_measurement: boolean;
  };
  safety_notice: string;
}
