# UI Gap Analysis

## Inventory

The dashboard has a single Streamlit entry point, a centralized HTTP helper, three presentation components, one view model, and theme CSS. It currently renders a Command Center and a case-workspace shell only.

## Gaps and Violations

- No page modules, app shell, breadcrumbs, typed API response contracts, state wrapper, feature containers, or demo adapter exist.
- The API exposes only empty paginated envelopes for all clinical resources; no case-detail, command, upload, AI-result, workflow, or audit contract exists.
- Command Center filters are visual controls only. Case tabs are controlled unavailable states, not connected features.
- There are no API error classes, retry policy, actor propagation, idempotency lifecycle, stale version UX, loading skeletons, AppTest, browser, accessibility, or visual tests.
- No dashboard component currently fetches data directly, but the entry point mixes fetch coordination and layout. This is acceptable only as a temporary feature container.

## Safety and Accessibility

Current language correctly avoids AI diagnosis, ECG-only rule-out, and autonomous cath-lab activation. The research-use label is present but no persistent watermark, keyboard navigation validation, or contrast audit exists.

## Implementation Plan

1. Stabilize the API client, typed models, session wrapper, app shell, and controlled states.
2. Provide explicit development demo mode with deterministic fixtures and persistent watermark.
3. Add actual UI panels only after versioned API case-detail/query and command contracts exist.
4. Add AppTest, Playwright/axe, and screenshot baselines once pages have real or demo fixture states.

## Blocking Backend Dependencies

`GET /api/v1/clinical-cases/{id}`, all case sub-resource queries, all command endpoints, upload handling, AI explanation media, model registry query, task/alert commands, timeline/audit query, actor context, idempotency, and optimistic-version contracts are absent.
