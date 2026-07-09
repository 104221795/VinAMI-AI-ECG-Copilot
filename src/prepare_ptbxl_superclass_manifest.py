"""Prepare PTB-XL 5-superclass multi-label manifest.

Output labels:
    NORM, MI, STTC, CD, HYP
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

import pandas as pd


SUPERCLASSES = ["NORM", "MI", "STTC", "CD", "HYP"]


def parse_scp_codes(value: str) -> dict[str, float]:
    parsed = ast.literal_eval(value)
    return {str(key): float(score) for key, score in parsed.items()}


def build_statement_to_superclass(scp_statements: pd.DataFrame) -> dict[str, str]:
    diagnostic = scp_statements[scp_statements["diagnostic"] == 1].copy()
    mapping: dict[str, str] = {}
    for code, row in diagnostic.iterrows():
        superclass = row.get("diagnostic_class")
        if isinstance(superclass, str) and superclass in SUPERCLASSES:
            mapping[str(code)] = superclass
    return mapping


def labels_from_codes(scp_codes: str, statement_to_superclass: dict[str, str]) -> dict[str, int]:
    labels = {name: 0 for name in SUPERCLASSES}
    for code in parse_scp_codes(scp_codes):
        superclass = statement_to_superclass.get(code)
        if superclass:
            labels[superclass] = 1
    return labels


def split_name(strat_fold: int) -> str:
    if strat_fold == 9:
        return "val"
    if strat_fold == 10:
        return "test"
    return "train"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ptbxl-root", type=Path, default=Path("data/ptb-xl"))
    parser.add_argument("--output", type=Path, default=Path("data/ptbxl_superclass_manifest.csv"))
    args = parser.parse_args()

    database_path = args.ptbxl_root / "ptbxl_database.csv"
    scp_path = args.ptbxl_root / "scp_statements.csv"
    if not database_path.exists():
        raise SystemExit(f"Missing {database_path}")
    if not scp_path.exists():
        raise SystemExit(f"Missing {scp_path}")

    db = pd.read_csv(database_path)
    scp = pd.read_csv(scp_path, index_col=0)
    statement_to_superclass = build_statement_to_superclass(scp)

    rows = []
    for _, row in db.iterrows():
        labels = labels_from_codes(row["scp_codes"], statement_to_superclass)
        output = {
            "ecg_id": int(row["ecg_id"]),
            "patient_id": int(row["patient_id"]),
            "filename_lr": row["filename_lr"],
            "filename_hr": row["filename_hr"],
            "strat_fold": int(row["strat_fold"]),
            "split": split_name(int(row["strat_fold"])),
            "age": row.get("age"),
            "sex": row.get("sex"),
        }
        output.update(labels)
        rows.append(output)

    manifest = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(args.output, index=False)

    print(f"Saved: {args.output}")
    print(f"Records: {len(manifest)}")
    print("Superclass counts:")
    for label in SUPERCLASSES:
        print(f"  {label}: {int(manifest[label].sum())}")
    print("Split counts:")
    print(manifest["split"].value_counts().to_string())


if __name__ == "__main__":
    main()

