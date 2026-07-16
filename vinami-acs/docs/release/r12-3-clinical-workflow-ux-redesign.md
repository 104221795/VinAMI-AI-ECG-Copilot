# R12.3 Clinical Workflow UX Redesign

Date: 2026-07-16

## Design-System Changes

- Added clinical serif typography for primary case titles and major clinical headings using `Cambria, Georgia, "Times New Roman", serif`.
- Preserved the VinAMI teal identity and existing restrained token palette.
- Added consistent workflow/status treatments for pending, available, under review, in progress, completed, overdue, failed and technically limited states.
- Added compact workflow board, branch card, AI path and scheduling-summary styles with solid surfaces, subtle borders and reduced-motion-safe CSS transitions.

## Navigation Changes

- The shared case header now supports a workflow status field when the owning route has that projection.
- Workflow route passes the persisted workflow state into the shared case header.
- Command Center selected-case quick view now links directly to Triage / Vitals as part of the case workspace navigation.
- R12.2 Triage / Vitals route remains the consistent documentation entry point.

## Workflow-Board Implementation

Added `ClinicalWorkflowBoard` in the Workflow bounded frontend feature.

The board presents:

- Patient and Encounter;
- Triage and Vitals;
- ECG Acquisition;
- ECG AI-supported Analysis;
- Physician ECG Interpretation;
- Troponin T0;
- Repeat Evidence;
- Clinical Evidence Snapshot;
- Physician Assessment;
- Physician Decision;
- Workflow and Tasks;
- Follow-up Scheduling;
- Outcome and Audit.

It separates:

- evidence stages;
- physician-authored authority;
- workflow tasks and alerts;
- scheduling representation.

The board is presentation-only. It does not create clinical conclusions, automatic pathway selection, cath-lab authority or autonomous scheduling.

## AI Path Representation

The ECG workspace now shows a clear AI-supported ECG path:

1. ECG acquired.
2. Technical quality check.
3. Model inference.
4. Model result and explanation.
5. Physician ECG review.
6. Evidence snapshot and physician decision.

The UI explicitly distinguishes machine-generated evidence from physician-authored interpretation and physician-authorized decisions. Model scores are not presented as disease probabilities.

## Scheduling Flow Representation

Case Overview and Workflow now show the follow-up scheduling concept:

- physician follow-up recommendation;
- administrative appointment request;
- staff review and confirmation;
- reminder/reschedule/cancel;
- missed/no-show or completed follow-up.

This remains a representation only. The MVP does not yet include an appointment model, hospital calendar engine or production scheduling integration.

## Accessibility and Responsiveness

- Workflow board uses semantic sections, ordered stage rail and accessible links to source workspaces.
- Status is shown with text, not color alone.
- Existing focus states and reduced-motion CSS remain active.
- Workflow board collapses to a vertical flow on smaller screens.
- Command Center table header is sticky inside the queue scroll area.

## Validation

Focused validation should include:

- Command Center -> selected case -> Triage / Vitals, ECG, Troponin, Reasoning, Workflow, Timeline and Audit.
- Workflow board with active repeat ECG/repeat troponin tasks.
- ECG AI path with mock/synthetic provider and physician review.
- Case Overview scheduling representation.
- Reduced-motion mode and keyboard navigation.

## Remaining UI or Functional Blockers

- No Framer Motion/Motion dependency exists in the frontend package, so R12.3 did not add motion-library animation.
- Scheduling is not backed by a real appointment/calendar bounded context.
- Outcome and follow-up state are still represented through timeline/outcome records, not a dedicated scheduling workspace.
- Production hospital integration remains out of scope; existing integration paths are simulated.

## Clinical Safety Statement

This redesign does not claim clinical validation or production hospital readiness. VinAMI remains a research-use clinical workflow MVP. AI is a replaceable support module, not the product authority.
