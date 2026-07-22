import { z } from "zod";

const historySchema = z.object({
  transition_id: z.string().uuid(),
  from_status: z.string(),
  to_status: z.string(),
  actor_id: z.string().uuid(),
  occurred_at: z.string(),
  reason: z.string().nullable(),
});

export const workflowTaskSchema = z.object({
  task_id: z.string().uuid(),
  case_id: z.string().uuid(),
  workflow_id: z.string().uuid().nullable(),
  task_type: z.string(),
  status: z.string(),
  priority: z.string(),
  version: z.number().int().positive(),
  created_at: z.string(),
  created_by: z.string().uuid().nullable(),
  due_at: z.string().nullable(),
  originating_decision_id: z.string().uuid().nullable(),
  source_type: z.string(),
  source_id: z.string().uuid().nullable(),
  owner_user_id: z.string().uuid().nullable(),
  owner_team_id: z.string().uuid().nullable(),
  acknowledged_at: z.string().nullable(),
  started_at: z.string().nullable(),
  completed_at: z.string().nullable(),
  outcome: z.string().nullable(),
  cancelled_at: z.string().nullable(),
  cancellation_reason: z.string().nullable(),
  overdue_at: z.string().nullable(),
  escalation_level: z.number().int().nonnegative(),
  history: z.array(historySchema),
  originating_decision: z
    .object({
      decision_id: z.string().uuid(),
      decision_type: z.string(),
      status: z.string(),
      recorded_at: z.string(),
      rationale: z.string(),
    })
    .nullable()
    .optional(),
});

export const workflowAlertSchema = z.object({
  alert_id: z.string().uuid(),
  case_id: z.string().uuid(),
  workflow_id: z.string().uuid().nullable(),
  task_id: z.string().uuid().nullable(),
  alert_type: z.string(),
  source: z.string(),
  severity: z.string(),
  message: z.string(),
  status: z.string(),
  version: z.number().int().positive(),
  raised_at: z.string(),
  acknowledged_at: z.string().nullable(),
  resolved_at: z.string().nullable(),
  resolution_reason: z.string().nullable(),
  escalation_level: z.number().int().nonnegative(),
  history: z.array(historySchema),
});

export const workflowOperationsSchema = z.object({
  case_id: z.string().uuid(),
  case_version: z.number().int().positive(),
  workflow: z.object({
    workflow_id: z.string().uuid(),
    state: z.string(),
    version: z.number().int().positive(),
    definition_version: z.string(),
    demonstration_notice: z.string(),
  }),
  tasks: z.array(workflowTaskSchema),
  alerts: z.array(workflowAlertSchema),
  alert_digest: z.array(z.record(z.string(), z.unknown())),
  safety_notice: z.string(),
});

export type WorkflowOperationsView = z.infer<typeof workflowOperationsSchema>;
export type WorkflowTaskView = z.infer<typeof workflowTaskSchema>;
export type WorkflowAlertView = z.infer<typeof workflowAlertSchema>;
