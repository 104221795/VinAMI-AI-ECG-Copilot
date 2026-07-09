"""Create PTB-XL dataset analysis tables and visualizations.

Inputs:
    - PTB-XL root folder with ptbxl_database.csv and scp_statements.csv
    - Optional superclass manifest produced by prepare_ptbxl_superclass_manifest.py

Outputs:
    - CSV summaries
    - PNG charts for reports/papers
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


SUPERCLASSES = ["NORM", "MI", "STTC", "CD", "HYP"]


def parse_scp_codes(value: str) -> dict[str, float]:
    return {str(key): float(score) for key, score in ast.literal_eval(value).items()}


def split_name(strat_fold: int) -> str:
    if strat_fold == 9:
        return "val"
    if strat_fold == 10:
        return "test"
    return "train"


def save_bar(series: pd.Series, title: str, xlabel: str, ylabel: str, output: Path, rotate: int = 0) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(9, 5), dpi=140)
    ax = series.plot(kind="bar", color="#3b82f6")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    plt.xticks(rotation=rotate, ha="right" if rotate else "center")
    plt.tight_layout()
    plt.savefig(output)
    plt.close()


def save_hist(values: pd.Series, title: str, xlabel: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(8, 5), dpi=140)
    plt.hist(values.dropna(), bins=30, color="#10b981", edgecolor="white")
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(output)
    plt.close()


def save_heatmap(matrix: pd.DataFrame, title: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(7, 6), dpi=140)
    plt.imshow(matrix.values, cmap="magma")
    plt.colorbar(label="Count")
    plt.xticks(range(len(matrix.columns)), matrix.columns, rotation=45, ha="right")
    plt.yticks(range(len(matrix.index)), matrix.index)
    plt.title(title)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            plt.text(j, i, str(int(matrix.iloc[i, j])), ha="center", va="center", color="white", fontsize=8)
    plt.tight_layout()
    plt.savefig(output)
    plt.close()


def build_superclass_manifest(db: pd.DataFrame, scp: pd.DataFrame) -> pd.DataFrame:
    diagnostic = scp[scp["diagnostic"] == 1].copy()
    statement_to_superclass: dict[str, str] = {}
    for code, row in diagnostic.iterrows():
        superclass = row.get("diagnostic_class")
        if isinstance(superclass, str) and superclass in SUPERCLASSES:
            statement_to_superclass[str(code)] = superclass

    rows = []
    for _, row in db.iterrows():
        labels = {name: 0 for name in SUPERCLASSES}
        for code in parse_scp_codes(row["scp_codes"]):
            superclass = statement_to_superclass.get(code)
            if superclass:
                labels[superclass] = 1
        rows.append(labels)

    labels_df = pd.DataFrame(rows)
    manifest = db[["ecg_id", "patient_id", "strat_fold", "age", "sex"]].copy()
    manifest["split"] = manifest["strat_fold"].apply(split_name)
    return pd.concat([manifest, labels_df], axis=1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ptbxl-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--outdir", type=Path, default=Path("reports/ptbxl_eda"))
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    db = pd.read_csv(args.ptbxl_root / "ptbxl_database.csv")
    scp = pd.read_csv(args.ptbxl_root / "scp_statements.csv", index_col=0)

    if args.manifest and args.manifest.exists():
        manifest = pd.read_csv(args.manifest)
    else:
        manifest = build_superclass_manifest(db, scp)

    summary_rows = {
        "records": len(db),
        "patients": db["patient_id"].nunique(),
        "female_count": int((db["sex"] == 0).sum()) if "sex" in db else np.nan,
        "male_count": int((db["sex"] == 1).sum()) if "sex" in db else np.nan,
        "age_mean": float(db["age"].mean()) if "age" in db else np.nan,
        "age_std": float(db["age"].std()) if "age" in db else np.nan,
    }
    pd.Series(summary_rows, name="value").to_csv(args.outdir / "dataset_summary.csv")

    split_counts = manifest["split"].value_counts().reindex(["train", "val", "test"])
    split_counts.to_csv(args.outdir / "split_counts.csv")
    save_bar(split_counts, "PTB-XL Split Counts", "Split", "Records", args.outdir / "split_counts.png")

    label_counts = manifest[SUPERCLASSES].sum(axis=0).sort_values(ascending=False)
    label_counts.to_csv(args.outdir / "superclass_counts.csv")
    save_bar(label_counts, "Diagnostic Superclass Counts", "Superclass", "Positive Records", args.outdir / "superclass_counts.png")

    label_percent = (label_counts / len(manifest) * 100).round(2)
    label_percent.to_csv(args.outdir / "superclass_percent.csv")
    save_bar(label_percent, "Diagnostic Superclass Percentage", "Superclass", "Percent of Records", args.outdir / "superclass_percent.png")

    cooccurrence = pd.DataFrame(index=SUPERCLASSES, columns=SUPERCLASSES, dtype=int)
    for left in SUPERCLASSES:
        for right in SUPERCLASSES:
            cooccurrence.loc[left, right] = int(((manifest[left] == 1) & (manifest[right] == 1)).sum())
    cooccurrence.to_csv(args.outdir / "superclass_cooccurrence.csv")
    save_heatmap(cooccurrence, "Superclass Co-occurrence", args.outdir / "superclass_cooccurrence.png")

    if "age" in db:
        save_hist(db["age"], "Patient Age Distribution", "Age", args.outdir / "age_distribution.png")
    if "sex" in db:
        sex_counts = db["sex"].value_counts().sort_index()
        sex_counts.index = [f"sex={idx}" for idx in sex_counts.index]
        sex_counts.to_csv(args.outdir / "sex_counts.csv")
        save_bar(sex_counts, "Sex Distribution", "Sex Code", "Records", args.outdir / "sex_counts.png")

    statement_counts: dict[str, int] = {}
    for codes in db["scp_codes"]:
        for code in parse_scp_codes(codes):
            statement_counts[code] = statement_counts.get(code, 0) + 1
    statement_series = pd.Series(statement_counts).sort_values(ascending=False)
    statement_series.to_csv(args.outdir / "scp_statement_counts.csv")
    save_bar(
        statement_series.head(30),
        "Top 30 SCP Statement Counts",
        "SCP Statement",
        "Records",
        args.outdir / "top30_scp_statement_counts.png",
        rotate=60,
    )

    print(f"Saved PTB-XL EDA report to: {args.outdir}")
    print("Key files:")
    print(f"  {args.outdir / 'dataset_summary.csv'}")
    print(f"  {args.outdir / 'superclass_counts.png'}")
    print(f"  {args.outdir / 'superclass_cooccurrence.png'}")


if __name__ == "__main__":
    main()

