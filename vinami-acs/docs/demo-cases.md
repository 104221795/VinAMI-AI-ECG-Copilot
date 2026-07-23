# VinAMI Demo Cases

This file explains how to run deterministic demo data for the VinAMI ACS Operating System.

VinAMI is a research-use MVP. These cases are synthetic demonstrations only. They are not clinical examples, not validated patient scenarios, and not for clinical use.

## 1. Start the system

From the repository root:

```powershell
cd vinami-acs
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api alembic upgrade head
```

Open:

```text
http://localhost:3000
```

Useful health checks:

```text
http://localhost:8000/health
http://localhost:8000/ready
```

## 2. Seed demo cases

Run:

```powershell
docker compose exec api python -m scripts.seed_demo_happy_cases
```

This creates deterministic synthetic cases through public FastAPI routes. The script does not bypass API validation, identity headers, audit hooks, or event dispatch.

If the UI is already open, refresh the Command Center after seeding.

## 3. Demo Case A - Complete ACS workflow case

Patient reference:

```text
VINAMI-DEMO-HAPPY-001
```

What this case demonstrates:

- patient and encounter creation;
- suspected ACS case creation;
- structured triage;
- complete vital signs;
- ECG upload using canonical demo waveform;
- ECG AI analysis through the mock ECG provider;
- physician ECG interpretation;
- serial troponin results;
- clinical reasoning snapshot;
- physician assessment and decision;
- workflow task generation;
- outcome record;
- timeline and audit visibility.

Where to view:

```text
http://localhost:3000/command-center
```

Then select the case with patient reference:

```text
VINAMI-DEMO-HAPPY-001
```

Recommended UI path:

1. Command Center
2. Selected case panel
3. Clinical Case Workspace
4. Triage / Vitals
5. ECG Workspace
6. Troponin Workspace
7. Clinical Reasoning
8. Workflow
9. Timeline
10. Audit

Expected result:

- the case should look mostly complete;
- evidence status should not show missing ECG, vitals, triage, or troponin;
- ECG should show AI-supported five-label output, not diagnosis;
- troponin should show serial results;
- workflow should show a generated operational task;
- timeline and audit should contain backend-generated records;
- outcome should be present.

## 4. Demo Case B - Missing outcome safety case

Patient reference:

```text
VINAMI-DEMO-MISSING-OUTCOME-001
```

What this case demonstrates:

- complete task does not automatically create outcome;
- workflow completion is not the same as clinical outcome;
- missing outcome remains missing until a physician records it;
- audit and timeline still preserve task activity.

Where to view:

```text
http://localhost:3000/command-center
```

Then select the case with patient reference:

```text
VINAMI-DEMO-MISSING-OUTCOME-001
```

Recommended UI path:

1. Command Center
2. Clinical Case Workspace
3. Workflow
4. Timeline
5. Audit

Expected result:

- task activity should be visible;
- outcome should remain missing;
- the UI must not imply that a completed task creates a clinical outcome;
- this case is useful for checking safety wording and audit behavior.

## 5. ECG AI showcase cases

The repository includes code paths for ECG AI productionization and PTB-XL showcase integration, including:

- strict ECG AI provider interface;
- real-model adapter path;
- precomputed showcase provider;
- model provenance;
- five ECG label scores;
- Grad-CAM or explanation artifact references;
- dynamic ECG comparison.

However, the large local artifacts are intentionally not pushed to GitHub:

```text
PTBXL/
VinStroke_ECG_artifacts/
*.pt
*.pth
*.onnx
```

Reason: these files are large dataset/model artifacts and should be distributed through a separate artifact channel such as Google Drive, Kaggle, PhysioNet download, or GitHub Release.

If the artifact folder is available locally, seed PTB-XL showcase cases with:

```powershell
docker compose exec api python -m scripts.seed_ptbxl_artifact_ecg_cases
```

Use these cases to inspect:

- ECG waveform preview;
- CWT/model input artifact;
- five-label ECG scores;
- Grad-CAM attention aid;
- model name, version, artifact checksum, and preprocessing provenance;
- R18 serial ECG comparison when two studies are available.

Safety expectation:

- ECG AI output is displayed as model score or AI-supported finding;
- ECG AI output is not displayed as AMI diagnosis;
- Grad-CAM is an attention aid, not causal clinical proof;
- AI does not create physician decision, cath-lab request, or case closure.

## 6. Troubleshooting

Check running services:

```powershell
docker compose ps
```

Check database tables:

```powershell
docker compose exec postgres psql -U vinami -d vinami_acs -c "\dt"
```

Backend logs:

```powershell
docker compose logs -f api
```

Frontend logs:

```powershell
docker compose logs -f web
```

Worker logs:

```powershell
docker compose logs -f worker
```

If seeded cases do not appear:

```powershell
docker compose exec api python -m scripts.seed_demo_happy_cases
docker compose logs --tail=100 api
docker compose logs --tail=100 worker
```

Do not use these demo cases for clinical judgment. They exist only to review product flow, architecture, safety boundaries, and AI-assist presentation.
