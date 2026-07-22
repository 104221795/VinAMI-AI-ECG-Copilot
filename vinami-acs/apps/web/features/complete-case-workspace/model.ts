import { z } from "zod";

const optionalRecord = z.record(z.string(), z.unknown()).nullable();
const automationSchema = z.object({
  policy_version: z.string(),
  safety_notice: z.string(),
  completeness: z.object({
    score: z.number().int(),
    status: z.string(),
    required_count: z.number().int(),
    current_count: z.number().int(),
    items: z.array(z.record(z.string(), z.unknown())),
    missing_evidence: z.array(z.string()),
    stale_evidence: z.array(z.string()),
    technical_limits: z.array(z.string()),
    not_negative_evidence_notice: z.string(),
  }),
  suggested_tasks: z.array(z.record(z.string(), z.unknown())),
  alert_digest: z.array(z.record(z.string(), z.unknown())),
});

export const completeCaseWorkspaceSchema = z.object({
  case_id: z.string().uuid(),
  encounter_id: z.string().uuid(),
  patient_id: z.string().uuid(),
  patient_reference: z.string(),
  patient_name: z.string().nullable(),
  age_band: z.string().nullable(),
  sex_at_birth: z.string().nullable(),
  location: z.string(),
  encounter_status: z.string(),
  case_status: z.string(),
  case_priority: z.string(),
  opening_reason: z.string(),
  opened_at: z.string(),
  last_updated_at: z.string(),
  case_version: z.number().int(),
  triage: optionalRecord,
  vitals: optionalRecord,
  ecg: optionalRecord,
  troponin: z.record(z.string(), z.unknown()),
  evidence_snapshot: optionalRecord,
  physician_assessment: optionalRecord,
  physician_decision: optionalRecord,
  workflow: optionalRecord,
  tasks: z.array(z.record(z.string(), z.unknown())),
  alerts: z.array(z.record(z.string(), z.unknown())),
  timeline: z.array(z.record(z.string(), z.unknown())),
  evidence_status: z.string(),
  missing_evidence: z.array(z.string()),
  stale_evidence: z.array(z.string()),
  technical_limits: z.array(z.string()),
  automation: automationSchema,
  update_token: z.string(),
  evaluated_at: z.string(),
});

export type CompleteCaseWorkspaceView = z.infer<
  typeof completeCaseWorkspaceSchema
>;
