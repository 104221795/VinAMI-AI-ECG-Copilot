"""Generate lightweight PTB-XL R23A showcase artifacts from the real best checkpoint."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from scripts.seed_ptbxl_artifact_ecg_cases import (
    LABELS,
    _read_representative_samples,
    _representative_waveform,
)
from vinami.ecg.adapters.precomputed_showcase_provider import PROVIDER_NAME
from vinami.ecg.adapters.torch_provider import (
    LABEL_MAPPING_VERSION,
    PREPROCESSING_VERSION,
    SAFE_DISPLAY_LABELS,
    TorchConvNeXtV2Provider,
)
from vinami.ecg.ports.provider import ECGExplanationRequest, ECGPredictionRequest

CHECKPOINT_SHA256 = "db43e0caedbcc579ea8a495dec1310066016d7ea55ad537e77bb4e5a48fc1837"


def main() -> None:
    args = _parse_args()
    provider = TorchConvNeXtV2Provider(
        args.checkpoint,
        args.checkpoint_sha256,
        args.device,
        args.timeout_seconds,
    )
    info = provider.get_model_info()
    exported_predictions = _read_exported_predictions(args.artifact_root)
    entries: list[dict[str, object]] = []
    for sample in _read_representative_samples(args.artifact_root):
        reference = f"PTBXL-R23A-SHOWCASE-{sample.label}-{sample.ecg_id:05d}"
        waveform_bytes = json.dumps(
            _representative_waveform(reference, sample),
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        study_id = uuid5(NAMESPACE_URL, f"vinami:ptbxl-r23a:{sample.label}:{sample.ecg_id}")
        prediction = provider.predict(
            ECGPredictionRequest(
                study_id,
                f"artifact://ptbxl-r23a-showcase/{sample.label}/{sample.ecg_id}",
                waveform_bytes=waveform_bytes,
                input_quality="acceptable",
                artifact_checksum=sha256(waveform_bytes).hexdigest(),
            )
        )
        explanation_label = sample.label
        label_scores = exported_predictions.get(sample.ecg_id, prediction.label_scores)
        predicted_findings = tuple(
            SAFE_DISPLAY_LABELS[label]
            for label in LABELS
            if label_scores[label] >= prediction.thresholds[label]
        )
        explanation = provider.explain(
            ECGExplanationRequest(
                study_id,
                f"artifact://ptbxl-r23a-showcase/{sample.label}/{sample.ecg_id}",
                explanation_label,
                waveform_bytes=waveform_bytes,
                input_quality="acceptable",
                artifact_checksum=sha256(waveform_bytes).hexdigest(),
            )
        )
        if not explanation.content or explanation.content_type != "image/png":
            raise RuntimeError(f"Grad-CAM generation failed for {sample.label} {sample.ecg_id}")
        image_relative = Path("reports") / f"r23a_gradcam_{sample.label}_ecg{sample.ecg_id}.png"
        image_path = args.artifact_root / image_relative
        image_path.write_bytes(explanation.content)
        entries.append(
            {
                "label": sample.label,
                "ecg_id": sample.ecg_id,
                "record_path": sample.record_path,
                "model_name": prediction.model_name,
                "model_version": prediction.model_version,
                "label_scores": label_scores,
                "thresholds": prediction.thresholds,
                "predicted_findings": list(predicted_findings),
                "explanation_label": explanation_label,
                "explanation_image": image_relative.as_posix(),
                "warnings": list(prediction.warnings),
                "provenance": {
                    **prediction.provenance,
                    "source_label": sample.label,
                    "source_ecg_id": str(sample.ecg_id),
                    "source_record_path": sample.record_path,
                    "showcase_generation_mode": "host-precomputed-from-best-model",
                    "showcase_explanation_target": sample.label,
                    "score_source": (
                        "reports/test_predictions.csv"
                        if sample.ecg_id in exported_predictions
                        else "provider inference on deterministic surrogate waveform"
                    ),
                    "explanation_image_sha256": sha256(explanation.content).hexdigest(),
                },
            }
        )
    manifest = {
        "schema_version": "vinami-ptbxl-r23a-showcase-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "provider_name": PROVIDER_NAME,
        "model_name": info.name,
        "model_version": info.version,
        "checkpoint_sha256": args.checkpoint_sha256,
        "preprocessing_version": PREPROCESSING_VERSION,
        "label_mapping_version": LABEL_MAPPING_VERSION,
        "threshold_source": info.threshold_source,
        "label_order": list(LABELS),
        "input_contract": info.input_contract,
        "safety_notice": (
            "Generated from best_model.pt for R23A research showcase. Model scores are "
            "not diagnoses or clinical probabilities."
        ),
        "entries": entries,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "manifest": str(args.out),
                "entries": len(entries),
                "provider": PROVIDER_NAME,
                "checkpoint_sha256": args.checkpoint_sha256,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2] / "VinStroke_ECG_artifacts"
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, default=root)
    parser.add_argument("--checkpoint", type=Path, default=root / "models" / "best_model.pt")
    parser.add_argument("--checkpoint-sha256", default=CHECKPOINT_SHA256)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument(
        "--out",
        type=Path,
        default=root / "reports" / "r23a_showcase_predictions.json",
    )
    return parser.parse_args()


def _read_exported_predictions(root: Path) -> dict[int, dict[str, float]]:
    path = root / "reports" / "test_predictions.csv"
    if not path.is_file():
        return {}
    predictions: dict[int, dict[str, float]] = {}
    with path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            try:
                ecg_id = int(float(str(row.get("ecg_id", ""))))
                predictions[ecg_id] = {
                    label: round(float(str(row[f"prob_{label}"])), 6) for label in LABELS
                }
            except (KeyError, TypeError, ValueError):
                continue
    return predictions


if __name__ == "__main__":
    main()
