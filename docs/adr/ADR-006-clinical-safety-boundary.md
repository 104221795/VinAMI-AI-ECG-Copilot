# ADR-006: Enforce an Explicit Clinical Safety Boundary

- **Status:** Accepted
- **Date:** 2026-07-13

## Decision

All rules are versioned transparent demonstration rules and visibly labelled **"Demonstration rule - not for clinical use."** The system records suggestions and review tasks only. It prohibits ECG-only AMI rule-out, AI-driven cath-lab activation, autonomous consequential action, and unaudited state transition.

## Rationale

The MVP lacks clinical validation, approved clinical protocols, integrated source systems, and governance required for clinical deployment.

## Consequences

- Clinical Reasoning outputs include facts used, ruleset version, conflicts, limitation text and review requirement.
- A physician confirmation is a typed precondition for cath-lab review and transfer requests.
- Conflicting ECG, troponin, and clinical data raises a review alert rather than producing a conclusion.

