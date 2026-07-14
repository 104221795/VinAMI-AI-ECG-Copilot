# R3 Baseline

Recorded: 2026-07-14 (Asia/Saigon)

## Runtime

- API `/ready`: `ready`, schema revision `a2c4e6f8b0d1`, development identity mode.
- Next.js `/api/health`: `healthy`.
- PostgreSQL, Redis, API, worker, Next.js, legacy Streamlit, and Prometheus containers are running.
- Alembic: `a2c4e6f8b0d1 (head)`.
- Outbox: 388 published events and zero unexpected dead-letter records.
- No Docker volume reset was performed.

## Existing ECG implementation

The current ECG context is a Sprint 3 scaffold. It persists a study reference, a coarse quality state, one replaceable AI result, and normalized findings. It has no R3 API, artifact store, ingestion job, waveform persistence, physician interpretation, serial comparison, or reminder lifecycle. The current repository replaces the single AI result on save, so it does not satisfy R3 immutable-analysis history.

## Research artifact verification

- Checkpoint: `../VinStroke_ECG_artifacts/models/best_model.pt` (outside the application repository).
- Size: 1,052,846,153 bytes.
- SHA-256: `db43e0caedbcc579ea8a495dec1310066016d7ea55ad537e77bb4e5a48fc1837`.
- Checkpoint epoch: 9; recorded best metric: 0.7217257030184403.
- Architecture metadata: `convnextv2_base`, 3-channel 224 x 224 input.
- Label order: `NORM`, `MI`, `STTC`, `CD`, `HYP`.
- Input configuration: 10 seconds at 100 Hz, 1,000 samples, CWT `morl`, scales 1-32.
- Threshold metadata is present in the checkpoint and matches the validation-threshold CSV.
- State dictionary has 380 tensors and a 5-output classifier head.
- Notebook evidence uses `timm 1.0.26`, PyTorch 2.10.0, and a Tesla T4 during training.
- The application container does not currently package PyTorch/timm or mount the checkpoint. A real-provider runtime smoke test has not yet been performed.

The existing reports are research evidence, not clinical validation. Model scores are not clinical probabilities. No model training or live hospital connection is part of R3.

## Initial gate state

- ECG Clinical Product Gate: open.
- Hospital ECG Integration Gate: open; only local/mock operation is expected.
- Dynamic ECG Gate: open.
- Existing Research Model Adapter Gate: conditional pending adapter and runtime smoke-test evidence.
