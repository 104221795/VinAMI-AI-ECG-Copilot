# Accessibility

F0 targets practical WCAG 2.2 AA behavior; it is not a formal certification.

Implemented controls include semantic landmarks, one route-level H1, labelled navigation and tables, keyboard-selectable queue rows, visible focus, text labels for status, reduced-motion support, skip-to-content, named icon controls, accessible disclosures and readable error actions.

Playwright runs axe rules tagged `wcag2a`, `wcag2aa` and `wcag22aa` on Command Center, case workspace, Timeline, Audit, System Health and Storybook operational states. The final executed suites reported no violations. Contrast discovered during browser validation was corrected before the final run.
