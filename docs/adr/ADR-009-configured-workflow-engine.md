# ADR-009: Configured Workflow Engine

**Status:** Accepted  
**Date:** 2026-07-13

## Context

VinAMI ACS needs an auditable operational workflow for suspected ACS cases. Encoding routing policy as a long nested conditional tree would make transitions, review requirements, and safety guards difficult to inspect, test, version, or replace.

## Decision

Use a modular-monolith workflow engine with:

- a versioned JSON demonstration definition validated into typed domain objects;
- explicit state, transition, guard, effect, command, and command-result types;
- a `ClinicalWorkflow` aggregate with optimistic concurrency, transition history, and command-id idempotency;
- PostgreSQL persistence for workflow state, receipts, timers, task/alert effects, and transactional outbox events;
- a worker-owned due-timer service which invokes normal idempotent commands.

Every definition must carry `Demonstration workflow — not for clinical use.` The definition must not contain unreviewed clinical thresholds.

## Consequences

The MVP can inspect, test, and replace a workflow definition without changing router or UI code. Safety guards make it impossible for the implemented graph to close a case from ECG-only input or request cath-lab review without a recorded physician decision.

This is not a clinical guideline engine and does not make a patient-level AMI decision. Future validation, clinician governance, API authorization, and external task/escalation adapters remain separate work.
