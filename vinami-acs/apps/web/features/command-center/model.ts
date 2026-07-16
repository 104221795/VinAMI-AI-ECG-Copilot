import { z } from "zod";

const taskSchema = z.object({
  task_id: z.string().uuid(),
  task_type: z.string(),
  status: z.string(),
  priority: z.string(),
  due_at: z.string().nullable(),
  overdue_at: z.string().nullable(),
  escalation_level: z.number().int(),
  owner_user_id: z.string().uuid().nullable(),
  owner_team_id: z.string().uuid().nullable(),
});

const alertSchema = z.object({
  alert_id: z.string().uuid(),
  alert_type: z.string(),
  severity: z.string(),
  status: z.string(),
  raised_at: z.string(),
  escalation_level: z.number().int(),
});

export const commandCenterPageSchema = z.object({
  items: z.array(
    z.object({
      case_id: z.string().uuid(),
      encounter_id: z.string().uuid(),
      patient_id: z.string().uuid(),
      patient_reference: z.string(),
      age_band: z.string().nullable(),
      sex_at_birth: z.string().nullable(),
      location: z.string(),
      case_status: z.string(),
      case_priority: z.string(),
      case_version: z.number().int(),
      opened_at: z.string(),
      workflow_id: z.string().uuid().nullable(),
      workflow_state: z.string().nullable(),
      workflow_version: z.number().int().nullable(),
      operational_priority: z.string(),
      priority_reason: z.string(),
      active_task_count: z.number().int(),
      overdue_task_count: z.number().int(),
      unresolved_alert_count: z.number().int(),
      next_due_at: z.string().nullable(),
      oldest_overdue_at: z.string().nullable(),
      owner_user_id: z.string().uuid().nullable(),
      owner_team_id: z.string().uuid().nullable(),
      snapshot_id: z.string().uuid().nullable(),
      snapshot_created_at: z.string().nullable(),
      evidence_status: z.string(),
      evidence_freshness: z.record(z.string(), z.string()),
      missing_evidence: z.array(z.string()),
      technical_limits: z.array(z.string()),
      decision_id: z.string().uuid().nullable(),
      decision_type: z.string().nullable(),
      decision_rationale: z.string().nullable(),
      decision_recorded_at: z.string().nullable(),
      latest_activity_at: z.string(),
      update_token: z.string(),
      tasks: z.array(taskSchema),
      alerts: z.array(alertSchema),
    }),
  ),
  page: z.number().int(),
  page_size: z.number().int(),
  total: z.number().int(),
  evaluated_at: z.string(),
});

export type CommandCenterPageView = z.infer<typeof commandCenterPageSchema>;
export type CommandCenterCaseView = CommandCenterPageView["items"][number];
