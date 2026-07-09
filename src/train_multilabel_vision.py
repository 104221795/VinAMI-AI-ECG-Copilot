"""Train a multi-label ECG vision classifier.

Input manifest must include:
    image_path, split, NORM, MI, STTC, CD, HYP
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms


LABELS = ["NORM", "MI", "STTC", "CD", "HYP"]


class ECGImageDataset(Dataset):
    def __init__(self, frame: pd.DataFrame, transform) -> None:
        self.frame = frame.reset_index(drop=True)
        self.transform = transform

    def __len__(self) -> int:
        return len(self.frame)

    def __getitem__(self, index: int):
        row = self.frame.iloc[index]
        image = Image.open(row["image_path"]).convert("RGB")
        labels = torch.tensor(row[LABELS].astype(float).to_numpy(), dtype=torch.float32)
        return self.transform(image), labels


def build_model(name: str, num_labels: int, pretrained: bool) -> nn.Module:
    if name == "resnet18":
        weights = models.ResNet18_Weights.DEFAULT if pretrained else None
        model = models.resnet18(weights=weights)
        model.fc = nn.Linear(model.fc.in_features, num_labels)
        return model
    if name == "resnet50":
        weights = models.ResNet50_Weights.DEFAULT if pretrained else None
        model = models.resnet50(weights=weights)
        model.fc = nn.Linear(model.fc.in_features, num_labels)
        return model
    if name == "convnext_tiny":
        weights = models.ConvNeXt_Tiny_Weights.DEFAULT if pretrained else None
        model = models.convnext_tiny(weights=weights)
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, num_labels)
        return model
    raise ValueError(f"Unsupported model: {name}")


def make_transforms():
    train_tfms = transforms.Compose(
        [
            transforms.Resize((256, 256)),
            transforms.RandomResizedCrop(224, scale=(0.90, 1.0)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )
    eval_tfms = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )
    return train_tfms, eval_tfms


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> dict[str, float]:
    model.eval()
    all_targets = []
    all_probs = []
    for images, targets in loader:
        logits = model(images.to(device))
        probs = torch.sigmoid(logits).cpu().numpy()
        all_probs.append(probs)
        all_targets.append(targets.numpy())

    y_true = np.concatenate(all_targets, axis=0)
    y_prob = np.concatenate(all_probs, axis=0)
    y_pred = (y_prob >= 0.5).astype(int)

    metrics: dict[str, float] = {}
    metrics["macro_f1"] = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    metrics["micro_f1"] = float(f1_score(y_true, y_pred, average="micro", zero_division=0))
    metrics["macro_auprc"] = float(average_precision_score(y_true, y_prob, average="macro"))
    metrics["micro_auprc"] = float(average_precision_score(y_true, y_prob, average="micro"))
    try:
        metrics["macro_auroc"] = float(roc_auc_score(y_true, y_prob, average="macro"))
        metrics["micro_auroc"] = float(roc_auc_score(y_true, y_prob, average="micro"))
    except ValueError:
        metrics["macro_auroc"] = float("nan")
        metrics["micro_auroc"] = float("nan")

    for idx, label in enumerate(LABELS):
        try:
            metrics[f"{label}_auroc"] = float(roc_auc_score(y_true[:, idx], y_prob[:, idx]))
            metrics[f"{label}_auprc"] = float(average_precision_score(y_true[:, idx], y_prob[:, idx]))
        except ValueError:
            metrics[f"{label}_auroc"] = float("nan")
            metrics[f"{label}_auprc"] = float("nan")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model", choices=["resnet18", "resnet50", "convnext_tiny"], default="resnet18")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--no-pretrained", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("models/vinstroke_ecg.pt"))
    args = parser.parse_args()

    frame = pd.read_csv(args.manifest)
    train_frame = frame[frame["split"] == "train"].copy()
    val_frame = frame[frame["split"] == "val"].copy()
    test_frame = frame[frame["split"] == "test"].copy()

    train_tfms, eval_tfms = make_transforms()
    train_loader = DataLoader(ECGImageDataset(train_frame, train_tfms), batch_size=args.batch_size, shuffle=True, num_workers=2)
    val_loader = DataLoader(ECGImageDataset(val_frame, eval_tfms), batch_size=args.batch_size, shuffle=False, num_workers=2)
    test_loader = DataLoader(ECGImageDataset(test_frame, eval_tfms), batch_size=args.batch_size, shuffle=False, num_workers=2)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(args.model, len(LABELS), pretrained=not args.no_pretrained).to(device)

    counts = train_frame[LABELS].sum(axis=0).to_numpy(dtype=np.float32)
    negatives = len(train_frame) - counts
    pos_weight = torch.tensor(negatives / np.maximum(counts, 1), dtype=torch.float32, device=device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    best_macro_auprc = -1.0

    print(f"Device: {device}")
    print(f"Train/val/test: {len(train_frame)}/{len(val_frame)}/{len(test_frame)}")
    print(f"Train label counts: {dict(zip(LABELS, counts.astype(int).tolist()))}")

    for epoch in range(1, args.epochs + 1):
        model.train()
        running_loss = 0.0
        for images, targets in train_loader:
            images = images.to(device)
            targets = targets.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = criterion(logits, targets)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * images.size(0)

        val_metrics = evaluate(model, val_loader, device)
        loss_value = running_loss / max(len(train_loader.dataset), 1)
        print(f"Epoch {epoch}: loss={loss_value:.4f} val={val_metrics}")

        if val_metrics["macro_auprc"] > best_macro_auprc:
            best_macro_auprc = val_metrics["macro_auprc"]
            torch.save({"model": model.state_dict(), "labels": LABELS, "args": vars(args)}, args.output)
            print(f"Saved best checkpoint: {args.output}")

    checkpoint = torch.load(args.output, map_location=device)
    model.load_state_dict(checkpoint["model"])
    test_metrics = evaluate(model, test_loader, device)
    print(f"Test: {test_metrics}")


if __name__ == "__main__":
    main()

