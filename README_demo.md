# VinStroke ECG Clinical Research Workspace

This local Streamlit workspace presents the current VinStroke ECG research prototype in a clinical workflow-oriented interface.

It demonstrates **AI-assisted ECG interpretation** for PTB-XL-style CWT 12-lead grid images. It is not a clinical diagnostic product.

> Research-use only. Not clinically validated. Not a substitute for physician diagnosis.

The Vinmec-inspired visual theme is an independent project design. It does not imply Vinmec affiliation, deployment approval, or clinical validation.

## Patient-Case Golden Path

1. Select a de-identified PTB-XL patient case with a packaged CWT grid, or upload a compatible CWT image.
2. Review all five outputs in one ranked triage table: abnormal screen-positive, near-threshold, normal-pattern support, then below threshold.
3. Inspect the raw 12-lead waveform and the exact CWT image in separate tabs.
4. Optionally inspect a label-specific Grad-CAM overlay on the CWT input.
5. Export the research review.

The default held-out PTB-XL test case opens its stored inference immediately. Dynamic inference is only run on demand; the first CPU run loads the 1 GB ConvNeXtV2 checkpoint. Changing the case clears old predictions and explanations.

## Workspace Areas

- **Patient case review:** the case-centered five-label triage, representation check and optional explanation workflow.
- **Research evidence:** case representations, dataset analysis, held-out validation and training artifacts with explicit roles.
- **System and safety:** model contract, label definitions, and interpretation safeguards.

## Required Artifacts

The app automatically looks for:

```text
VinStroke_ECG_artifacts/
  config.json
  models/
    best_model_lite.pt
    best_model.pt
    last_model.pt
  reports/
    test_metrics.csv
    per_class_metrics.csv
    calibration_metrics.csv
    inference_one_sample.csv
    test_predictions.csv
    raw_12lead_*.png
    inference_cwt_grid_*.png
    ecg*_cwt_grid.png
    ecg*_stft_grid.png
    explainability_*.png
```

`inference_cwt_grid_*.png` and `ecg*_cwt_grid.png` are the only packaged image names accepted as CWT model inputs. `raw_12lead_*.png` and `spatial_12lead_*.png` are waveform visuals; they are never sent to the current vision checkpoint.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If your PyTorch install needs a CUDA-specific wheel, install PyTorch from the official selector first, then run the command above.

## Run

```powershell
.\run_demo.cmd
```

The script uses port `8502` by default:

```text
http://127.0.0.1:8502
```

To choose another port:

```powershell
$env:VINSTROKE_STREAMLIT_PORT = "8503"
.\run_demo.cmd
```

`run_demo.cmd` is the recommended Windows launcher because it does not depend on the local PowerShell execution policy. `run_demo.ps1` remains available when PowerShell scripts are permitted.

## Output Meaning

- **Model score:** an independent sigmoid output for one diagnostic superclass. It is not disease probability or severity.
- **Screen positive:** the score meets or exceeds that class's optimized validation threshold.
- **Below threshold:** the score does not meet that class's threshold; this does not exclude disease.
- **Near threshold:** the score is within 0.10 of its decision threshold and is highlighted for review.
- **Held-out evidence:** the test F1 shown beside each label exposes uneven model performance. HYP is the weakest label in this experiment.
- **Grad-CAM:** a low-resolution, label-specific attention overlay on the CWT image. It is not a signal amplitude map, lesion location or causal explanation.

## Limitations

- This is a research prototype.
- It is not clinically validated.
- It does not diagnose disease.
- It does not predict stroke.
- It should not be used as a substitute for physician diagnosis.
