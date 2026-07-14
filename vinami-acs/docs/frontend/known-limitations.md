# Known Limitations

- Production authentication and OIDC were not exercised; F0 uses a controlled predefined development identity.
- The R1 collection API lacks a joined queue read model, so F0 enriches each case with Encounter and Patient reads. A dedicated backend projection is recommended before scale testing.
- Search applies to the current server page because R1 has no server-side patient/case search contract.
- Assigned team is not returned by R1 and is not displayed.
- Worker status and migration revision are shown only when safely exposed; unavailable fields are explicitly labelled.
- Triage, vitals, ECG, troponin, reasoning, tasks, alerts and clinical commands are outside F0.
- No WebSocket/SSE is used; freshness is bounded refresh, not real-time monitoring.
- Bundle and page measurements are engineering baselines, not production performance certification.
- Accessibility checks are automated evidence, not formal certification.
- The system is not production-ready or clinically validated and must not be used for patient-care decisions.
