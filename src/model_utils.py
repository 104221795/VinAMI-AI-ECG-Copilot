from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from PIL import Image

DEFAULT_LABELS = ["NORM", "MI", "STTC", "CD", "HYP"]
DEFAULT_MODEL_NAME = "convnextv2_base"


def find_artifact_root(project_root: Path | str = ".") -> Path:
    root = Path(project_root)
    candidates = [
        root / "VinStroke_ECG_artifacts",
        root / "vinstroke_ECG_artifacts",
        root / "artifacts",
        root,
    ]
    for candidate in candidates:
        if (candidate / "models").exists() or (candidate / "reports").exists() or (candidate / "config.json").exists():
            return candidate
    return root / "VinStroke_ECG_artifacts"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def choose_checkpoint(artifact_root: Path) -> Path | None:
    candidates = [
        artifact_root / "models" / "best_model_lite.pt",
        artifact_root / "models" / "best_model.pt",
        artifact_root / "models" / "last_model.pt",
    ]
    return next((path for path in candidates if path.exists()), None)


def load_checkpoint_metadata(checkpoint_path: Path | None) -> dict[str, Any]:
    if checkpoint_path is None or not checkpoint_path.exists():
        return {}
    ckpt = torch.load(checkpoint_path, map_location="cpu")
    if not isinstance(ckpt, dict):
        return {}
    return {
        "epoch": ckpt.get("epoch"),
        "best_metric": ckpt.get("best_metric"),
        "label_names": ckpt.get("label_names"),
        "config": ckpt.get("config", {}),
        "threshold": ckpt.get("threshold", {}),
    }


def get_label_names(config: dict[str, Any], checkpoint_meta: dict[str, Any] | None = None) -> list[str]:
    checkpoint_meta = checkpoint_meta or {}
    labels = checkpoint_meta.get("label_names") or config.get("label_names") or DEFAULT_LABELS
    return [str(label) for label in labels]


def get_image_size(config: dict[str, Any], checkpoint_meta: dict[str, Any] | None = None) -> int:
    checkpoint_meta = checkpoint_meta or {}
    ckpt_config = checkpoint_meta.get("config") or {}
    return int(ckpt_config.get("image_size") or config.get("image_size") or 224)


def normalize_model_name(name: str | None) -> str:
    if not name:
        return DEFAULT_MODEL_NAME
    name = name.strip()
    aliases = {
        "convnextv2_base": "convnextv2_base.fcmae_ft_in22k_in1k",
        "convnextv2_tiny": "convnextv2_tiny.fcmae_ft_in22k_in1k",
        "convnext_tiny": "convnext_tiny.fb_in22k_ft_in1k",
    }
    return aliases.get(name, name)


def create_model(model_name: str, num_labels: int):
    try:
        import timm
    except ImportError as exc:
        raise RuntimeError("Missing dependency 'timm'. Install requirements.txt before live inference.") from exc

    normalized = normalize_model_name(model_name)
    try:
        return timm.create_model(normalized, pretrained=False, num_classes=num_labels)
    except Exception:
        # Some checkpoints were trained with the short timm model id.
        return timm.create_model(model_name, pretrained=False, num_classes=num_labels)


def strip_module_prefix(state_dict: dict[str, Any]) -> dict[str, Any]:
    if not any(key.startswith("module.") for key in state_dict):
        return state_dict
    return {key.removeprefix("module."): value for key, value in state_dict.items()}


def load_model(checkpoint_path: Path, config: dict[str, Any], device: str | torch.device = "cpu"):
    ckpt = torch.load(checkpoint_path, map_location=device)
    if not isinstance(ckpt, dict):
        raise RuntimeError(f"Unsupported checkpoint format: {checkpoint_path}")
    ckpt_config = ckpt.get("config", {}) or {}
    labels = ckpt.get("label_names") or ckpt_config.get("label_names") or config.get("label_names") or DEFAULT_LABELS
    model_name = ckpt_config.get("model_name") or config.get("model_name") or DEFAULT_MODEL_NAME
    model = create_model(model_name, len(labels))
    state = ckpt.get("model_state_dict") or ckpt.get("model") or ckpt
    model.load_state_dict(strip_module_prefix(state), strict=False)
    model.to(device)
    model.eval()
    return model, [str(label) for label in labels], ckpt


def load_thresholds(artifact_root: Path, labels: list[str], ckpt: dict[str, Any] | None = None) -> dict[str, float]:
    thresholds = {label: 0.5 for label in labels}
    if ckpt and isinstance(ckpt.get("threshold"), dict):
        thresholds.update({label: float(ckpt["threshold"].get(label, thresholds[label])) for label in labels})

    threshold_files = [
        artifact_root / "reports" / "optimized_thresholds_from_validation.csv",
        artifact_root / "reports" / "validation_optimized_thresholds.csv",
    ]
    for path in threshold_files:
        if not path.exists():
            continue
        df = pd.read_csv(path)
        label_col = "label" if "label" in df.columns else df.columns[0]
        threshold_col = "best_threshold" if "best_threshold" in df.columns else "threshold"
        if threshold_col not in df.columns:
            continue
        for _, row in df.iterrows():
            label = str(row[label_col])
            if label in thresholds:
                thresholds[label] = float(row[threshold_col])
        break
    return thresholds


def predict_image(model, image: Image.Image, transform, labels: list[str], device: str | torch.device = "cpu") -> pd.DataFrame:
    tensor = transform(image.convert("RGB")).unsqueeze(0).to(device)
    with torch.no_grad():
        logits = model(tensor)
        probs = torch.sigmoid(logits).detach().cpu().numpy()[0]
    return pd.DataFrame({"label": labels, "probability": probs.astype(float)})


def prediction_table(probabilities: pd.DataFrame, thresholds: dict[str, float]) -> pd.DataFrame:
    df = probabilities.copy()
    df["threshold"] = df["label"].map(lambda label: float(thresholds.get(str(label), 0.5)))
    df["decision"] = np.where(df["probability"] >= df["threshold"], "Screen positive", "Below threshold")
    df["threshold_margin"] = df["probability"] - df["threshold"]
    df["review_flag"] = np.where(
        df["threshold_margin"].abs() < 0.10,
        "Near threshold - review",
        np.where(df["threshold_margin"] >= 0, "Above threshold", "Below threshold"),
    )
    return df
