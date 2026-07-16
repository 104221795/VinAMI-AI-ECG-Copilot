# R3 Dynamic ECG and Repeat Workflow

## Comparability

The comparison policy evaluates waveform availability, lead overlap/order, sampling rate, amplitude unit, calibration context, duration, quality, preprocessing and model provenance. Results are `comparable`, `comparable_with_warning`, `partially_comparable`, `non_comparable` or `unknown`, with typed reasons shown before metrics.

Per-lead metrics are waveform similarity, normalized difference, amplitude scale change, baseline shift, missing-data percentage, quality difference and sample alignment. They are deterministic technical indicators, not diagnosis or disease progression.

Score deltas are shown only when finding codes, model family/version, preprocessing, label mapping and threshold provenance are compatible. Scores are not clinical probabilities.

## Physician Review

Each comparison is immutable. Physician review is append-only, actor-bound and versioned; correction creates a superseding record. Timeline and Audit receive versioned events through the transactional outbox.

## Repeat ECG

The lifecycle is scheduled, due/overdue, acknowledged, completed or cancelled. Completion must reference a later ECG. AI output cannot schedule a reminder or obtain workflow authority. All actions require an allowed clinical actor, idempotency and optimistic concurrency.
