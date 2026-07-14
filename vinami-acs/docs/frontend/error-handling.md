# Error and Data-State Handling

The API adapter classifies authentication, authorization, not found, conflict, validation, timeout, offline, server, malformed and unknown failures. Presentation mapping supplies a plain-language title, safe next action, retry policy, timestamp and correlation ID without exposing routes, SQL, source paths or stack traces.

Initial loading, refetching, empty, partial projection, stale, offline and eventual-consistency states are distinct. Failed Patient or Encounter enrichment marks only the affected queue row as partial. A malformed success response is withheld and shown as a contract mismatch.

Controlled Playwright tests cover 401, 403, 404, 500, malformed JSON shape, browser offline and an empty timeline projection. Safe GETs may retry once for transient 502/503/504; clinical commands are not present and are never auto-retried.
