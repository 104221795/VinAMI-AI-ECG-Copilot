# R23A — Real ECG Model Integration, Quality and Provenance

## Scope

R23A connects the existing PTB-XL ConvNeXtV2 ECG research checkpoint to VinAMI through the
`ECGAIProvider` port. The ECG model remains a replaceable module. It does not own triage,
workflow state, physician decisions, task creation, cath-lab review, discharge or AMI rule-out.

All model outputs are research-use model scores. They are not diagnoses and are not clinical
probabilities.

## Provider Contract

The real provider is `TorchConvNeXtV2Provider`.

Required input contract:

- VinAMI canonical waveform JSON or verified 224x224 RGB CWT image.
- 12 standard leads in this order: `I, II, III, aVR, aVL, aVF, V1, V2, V3, V4, V5, V6`.
- Sampling rate: `100 Hz`.
- Duration: `10 seconds`.
- Samples per lead: `1000`.
- Normalized amplitude unit: `uV`.

The provider rejects malformed waveform JSON, missing leads, wrong lead order, wrong sampling
rate, wrong sample length, non-finite values, flat lead data and unsupported amplitude ranges before
inference.

## Fixed Five-Label Mapping

The checkpoint label order is required to be exactly:

| Checkpoint code | Display label |
| --- | --- |
| `NORM` | `NORM` |
| `MI` | `MI-related ECG pattern` |
| `STTC` | `ST/T change` |
| `CD` | `conduction disturbance` |
| `HYP` | `hypertrophy pattern` |

## Provenance Captured

Persisted ECG analysis records capture:

- provider name and provider version;
- model name and model version;
- checkpoint SHA-256 checksum;
- preprocessing version;
- label-mapping version;
- threshold source;
- input artifact ID;
- input artifact checksum;
- quality status;
- execution duration;
- warnings and failure category when present.

## Runtime Configuration

Docker remains mock-first to keep the default MVP lightweight.

To run the real provider in a Python environment that already has `torch`, `torchvision` and `timm`:

```powershell
$env:VINAMI_ECG_PROVIDER="torch"
$env:VINAMI_ECG_CHECKPOINT_PATH="D:\MyNewDesktop\VinStroke\VinStroke_ECG_artifacts\models\best_model.pt"
$env:VINAMI_ECG_CHECKPOINT_SHA256="db43e0caedbcc579ea8a495dec1310066016d7ea55ad537e77bb4e5a48fc1837"
$env:VINAMI_ECG_DEVICE="cpu"
```

Fallback is disabled by default. If enabled with `VINAMI_ECG_ALLOW_PROVIDER_FALLBACK=true`, fallback
is explicit and the persisted AI result records the fallback warning.

## Lightweight Best-Checkpoint Showcase

For local UI demonstration without installing PyTorch inside Docker, R23A also supports the
`ptbxl-showcase` provider. This provider reads precomputed outputs generated from
`best_model.pt`:

- manifest: `VinStroke_ECG_artifacts/reports/r23a_showcase_predictions.json`;
- Grad-CAM PNGs: `VinStroke_ECG_artifacts/reports/r23a_gradcam_*`;
- provider name: `ptbxl-r23a-precomputed-best-pt-showcase`;
- `synthetic=false`, because the model output was generated from the verified checkpoint, not the
  mock provider.

Generate or refresh the precomputed showcase artifacts:

```powershell
$env:PYTHONPATH=".;src"
..\.venv\Scripts\python.exe scripts/build_ptbxl_r23a_showcase_artifacts.py --device cpu
```

Seed five visible showcase cases in the development physician location:

```powershell
$env:PYTHONPATH=".;src"
..\.venv\Scripts\python.exe scripts/seed_ptbxl_artifact_ecg_cases.py `
  --run-id r23a-bestpt-v2 `
  --location "Emergency Department" `
  --provider ptbxl-showcase `
  --fallback-provider mock
```

This mode is a fast persisted showcase, not live inference. It keeps the clinical boundary intact:
the model does not create tasks, decisions, cath-lab actions or AMI rule-out.

## PTB-XL Artifact-Backed Demo Cases

Use `scripts/seed_ptbxl_artifact_ecg_cases.py` to create five UI showcase cases from
`VinStroke_ECG_artifacts/reports/representative_samples.csv`.

The local artifact package contains checkpoint, reports, images and manifests, but it does not
contain the original PTB-XL WFDB `.dat/.hea` waveform files. Therefore the seed script creates
deterministic canonical waveform surrogates tagged with PTB-XL representative metadata and parser
warnings. This is suitable for UI/API integration demonstration, but it is not a replacement for
source-level PTB-XL waveform validation.

Example:

```powershell
python scripts/seed_ptbxl_artifact_ecg_cases.py --provider mock
```

Use `--provider torch` only when the running API has the real provider configured. Use
`--provider ptbxl-showcase` for the lightweight persisted best-checkpoint showcase.
