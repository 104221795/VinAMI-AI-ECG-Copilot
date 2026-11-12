"""Skeleton pipeline for VinStroke-ECG-LVEF label extraction and QC
(see Research/VinStroke_ECG_LVEF_Research_Proposal.md, section 8-9-Phase 1).

This is a SKELETON: no MIMIC-IV data is available locally yet, so the
regex/parsing/matching/QC-sampling logic below is fully implemented and
self-testable (`--selftest`), but the `extract`/`match`/`sample-qc`
subcommands expect real CSV exports from MIMIC-IV-ECG and MIMIC-IV-ECHO
(or MIMIC-IV-Note) once PhysioNet access/DUA is in place.

Expected input schemas (VERIFY against the actual data dictionary once
access is granted -- column names below are best-effort based on the
public MIMIC-IV-ECG / MIMIC-IV-ECHO documentation, not confirmed locally):

  notes CSV   (MIMIC-IV-ECHO report table, or MIMIC-IV-Note as fallback)
      subject_id, note_id (or study_id), charttime, text

  ecg CSV     (MIMIC-IV-ECG record list)
      subject_id, study_id, ecg_time

Pipeline stages (each a subcommand, run independently once inputs exist):

  extract    notes CSV  -> one row per note with regex-extracted LVEF
  match      ecg CSV + extract output -> ECG rows paired with nearest LVEF
  sample-qc  match output -> stratified sample for manual review
  score-qc   sample-qc output + filled-in manual_lvef column -> agreement report

MVP scope: the trained model answers exactly one question, "LVEF <= 40%?"
(binary), not a continuous LVEF regression. `lvef_numeric` is still extracted
here because it is needed for label-extraction QC (score_qc's MAE) and kept
as a future-work hook, but `lvef_binary_40` is the label that actually feeds
model training -- it is populated even for qualitative-only mentions
("severely reduced EF") that carry no exact number, which is why scoping
down to binary-only increases usable data volume versus requiring a number.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Stage 1: regex/qualitative extraction (proposal section "Bước 1-3")
# ---------------------------------------------------------------------------

# Numeric patterns, ordered as a fallback chain: first pattern that matches
# in a section deemed authoritative ("Left Ventricular Function", "Impression",
# "Conclusion") wins. If no section header is found, the chain is applied to
# the whole text and the LAST match is kept (most recent statement in a
# dictated report tends to be the final assessment).
NUMERIC_PATTERNS = [
    re.compile(r"(?:LVEF|EF)\s*(?:is|of|was|:)?\s*(\d{1,2})\s*-\s*(\d{1,2})\s*%"),
    re.compile(r"(?:LVEF|EF)\s*(?:is|of|was|:)?\s*(\d{1,2})\s*%"),
    re.compile(r"ejection fraction\s*(?:is|of|was|:)?\s*(\d{1,2})\s*-\s*(\d{1,2})\s*%"),
    re.compile(r"ejection fraction\s*(?:is|of|was|:)?\s*(\d{1,2})\s*%"),
    re.compile(r"ejection fraction\s*(?:is|of|was|:)?\s*(\d{1,2})\s*percent"),
]

SECTION_HEADERS = [
    "left ventricular function",
    "impression",
    "conclusion",
]

# Qualitative-only mentions (no number) mapped to a coarse bucket. Used only
# for the binary screening label (the only label the MVP model trains on) --
# see proposal section "Bước 2".
QUALITATIVE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(normal|preserved)\s+(?:LV|left ventricular)?\s*ef", re.I), "normal"),
    (re.compile(r"\bmildly reduced ef", re.I), "mild"),
    (re.compile(r"\bmoderately reduced ef", re.I), "moderate"),
    (re.compile(r"\bseverely reduced ef", re.I), "severe"),
]

QUALITATIVE_TO_BINARY = {
    "normal": 0,
    "mild": None,  # too close to the 40% threshold -- exclude from binary label
    "moderate": 1,
    "severe": 1,
}

PHYSIOLOGIC_MIN, PHYSIOLOGIC_MAX = 5, 85


@dataclass
class LvefExtraction:
    lvef_numeric: float | None
    lvef_binary_40: int | None  # 1 = LVEF <= 40, 0 = LVEF > 40, None = unknown/excluded
    source: str  # "numeric" | "qualitative" | "none"
    matched_snippet: str | None


def _find_section_window(text: str) -> str:
    """Return the text after the first authoritative section header, if any,
    else the full text. Keeps ~300 chars, enough for one EF statement."""
    lower = text.lower()
    for header in SECTION_HEADERS:
        idx = lower.find(header)
        if idx != -1:
            return text[idx : idx + 300]
    return text


def extract_lvef(text: str) -> LvefExtraction:
    if not text or not isinstance(text, str):
        return LvefExtraction(None, None, "none", None)

    window = _find_section_window(text)

    for pattern in NUMERIC_PATTERNS:
        matches = list(pattern.finditer(window))
        if not matches:
            continue
        m = matches[-1]  # last match in the authoritative window
        groups = [g for g in m.groups() if g is not None]
        if len(groups) == 2:
            value = min(int(groups[0]), int(groups[1]))  # conservative: lower bound of range
        else:
            value = int(groups[0])
        if not (PHYSIOLOGIC_MIN <= value <= PHYSIOLOGIC_MAX):
            continue
        return LvefExtraction(
            lvef_numeric=float(value),
            lvef_binary_40=int(value <= 40),
            source="numeric",
            matched_snippet=m.group(0),
        )

    for pattern, bucket in QUALITATIVE_PATTERNS:
        m = pattern.search(window)
        if m:
            return LvefExtraction(
                lvef_numeric=None,
                lvef_binary_40=QUALITATIVE_TO_BINARY[bucket],
                source="qualitative",
                matched_snippet=m.group(0),
            )

    return LvefExtraction(None, None, "none", None)


def cmd_extract(args: argparse.Namespace) -> None:
    notes = pd.read_csv(args.notes_csv)
    results = notes[args.text_col].apply(extract_lvef)
    out = pd.DataFrame(
        {
            args.id_col: notes[args.id_col],
            "subject_id": notes["subject_id"],
            "charttime": notes["charttime"],
            "lvef_numeric": [r.lvef_numeric for r in results],
            "lvef_binary_40": [r.lvef_binary_40 for r in results],
            "source": [r.source for r in results],
            "matched_snippet": [r.matched_snippet for r in results],
        }
    )
    out.to_csv(args.out, index=False)
    n_numeric = (out["source"] == "numeric").sum()
    n_qual = (out["source"] == "qualitative").sum()
    n_none = (out["source"] == "none").sum()
    print(
        f"extracted {len(out)} notes: {n_numeric} numeric, {n_qual} qualitative-only, "
        f"{n_none} no match ({n_none / len(out):.1%})"
    )


# ---------------------------------------------------------------------------
# Stage 2: time-window matching (proposal section "Bước 4")
# ---------------------------------------------------------------------------


def match_ecg_to_lvef(
    ecg: pd.DataFrame, lvef: pd.DataFrame, max_days: int
) -> pd.DataFrame:
    """For each ECG row, attach the closest-in-time LVEF extraction from the
    same subject_id within `max_days`. O(n log n) via per-subject merge_asof."""
    ecg = ecg.copy()
    lvef = lvef.dropna(subset=["lvef_numeric", "lvef_binary_40"], how="all").copy()
    ecg["ecg_time"] = pd.to_datetime(ecg["ecg_time"])
    lvef["charttime"] = pd.to_datetime(lvef["charttime"])

    matched_parts = []
    for subject_id, ecg_group in ecg.groupby("subject_id"):
        lvef_group = lvef[lvef["subject_id"] == subject_id]
        if lvef_group.empty:
            continue
        left = ecg_group.sort_values("ecg_time")
        right = lvef_group.sort_values("charttime")
        merged = pd.merge_asof(
            left,
            right,
            left_on="ecg_time",
            right_on="charttime",
            direction="nearest",
            suffixes=("", "_lvef"),
        )
        merged["time_delta_days"] = (
            merged["ecg_time"] - merged["charttime"]
        ).abs().dt.total_seconds() / 86400
        matched_parts.append(merged)

    if not matched_parts:
        return ecg.iloc[0:0]

    result = pd.concat(matched_parts, ignore_index=True)
    result = result[result["time_delta_days"] <= max_days]
    return result


def cmd_match(args: argparse.Namespace) -> None:
    ecg = pd.read_csv(args.ecg_csv)
    lvef = pd.read_csv(args.lvef_csv)
    matched = match_ecg_to_lvef(ecg, lvef, max_days=args.max_days)
    matched.to_csv(args.out, index=False)
    n_subjects = matched["subject_id"].nunique()
    print(
        f"matched {len(matched)} ECG rows across {n_subjects} subjects "
        f"(max_days={args.max_days}, coverage={len(matched) / len(ecg):.1%} of ECGs)"
    )


# ---------------------------------------------------------------------------
# Stage 3: stratified QC sampling (proposal section "Bước 5")
# ---------------------------------------------------------------------------

QC_BINS = [(-np.inf, 30), (30, 40), (40, 50), (50, 60), (60, np.inf)]
QC_BIN_LABELS = ["<30", "30-40", "40-50", "50-60", ">60"]


def build_qc_sample(matched: pd.DataFrame, n_per_bin: int, seed: int) -> pd.DataFrame:
    numeric = matched.dropna(subset=["lvef_numeric"]).copy()
    numeric["bin"] = pd.cut(
        numeric["lvef_numeric"], bins=[b[0] for b in QC_BINS] + [QC_BINS[-1][1]], labels=QC_BIN_LABELS
    )
    rng = np.random.default_rng(seed)
    samples = []
    for label in QC_BIN_LABELS:
        bucket = numeric[numeric["bin"] == label]
        n = min(n_per_bin, len(bucket))
        if n < n_per_bin:
            print(f"warning: bin {label} only has {len(bucket)} rows, wanted {n_per_bin}")
        samples.append(bucket.sample(n=n, random_state=rng.integers(0, 2**32 - 1)))
    qc = pd.concat(samples, ignore_index=True)
    qc["manual_lvef"] = ""
    qc["manual_binary_40"] = ""
    qc["reviewer_notes"] = ""
    return qc


def cmd_sample_qc(args: argparse.Namespace) -> None:
    matched = pd.read_csv(args.matched_csv)
    qc = build_qc_sample(matched, n_per_bin=args.n_per_bin, seed=args.seed)
    qc.to_csv(args.out, index=False)
    print(f"wrote {len(qc)} rows to review at {args.out}")


# ---------------------------------------------------------------------------
# Stage 4: QC agreement scoring (proposal section "Bước 5", ngưỡng chấp nhận)
# ---------------------------------------------------------------------------


def score_qc(qc_filled: pd.DataFrame) -> dict:
    reviewed = qc_filled.dropna(subset=["manual_lvef"])
    reviewed = reviewed[reviewed["manual_lvef"] != ""]
    if reviewed.empty:
        raise ValueError("no rows with manual_lvef filled in -- nothing to score")

    manual = reviewed["manual_lvef"].astype(float)
    auto = reviewed["lvef_numeric"].astype(float)
    mae = float((manual - auto).abs().mean())
    near_match_rate = float(((manual - auto).abs() <= 5).mean())

    manual_binary = (manual <= 40).astype(int)
    auto_binary = reviewed["lvef_binary_40"].astype(int)
    agree = manual_binary == auto_binary
    po = agree.mean()  # observed agreement
    p_manual_pos = manual_binary.mean()
    p_auto_pos = auto_binary.mean()
    pe = p_manual_pos * p_auto_pos + (1 - p_manual_pos) * (1 - p_auto_pos)  # chance agreement
    kappa = float((po - pe) / (1 - pe)) if pe != 1 else float("nan")

    return {
        "n_reviewed": len(reviewed),
        "mae": mae,
        "near_match_rate_within_5pct": near_match_rate,
        "binary_40_cohens_kappa": kappa,
        "binary_40_observed_agreement": float(po),
    }


def cmd_score_qc(args: argparse.Namespace) -> None:
    qc_filled = pd.read_csv(args.qc_csv)
    report = score_qc(qc_filled)
    for k, v in report.items():
        print(f"{k}: {v}")
    if report["binary_40_cohens_kappa"] < 0.8:
        print(
            "WARNING: kappa < 0.8 -- per proposal section 5, revise regex/rules "
            "and re-run QC on a FRESH sample before using labels for training."
        )


# ---------------------------------------------------------------------------
# Self-test with synthetic report text (no MIMIC access required)
# ---------------------------------------------------------------------------


def _selftest() -> None:
    cases = [
        ("Left ventricular function: EF is 45%.", 45.0, 0),
        ("Impression: LVEF 30-35%, severely depressed.", 30.0, 1),
        ("EF of 62 % , normal left ventricular systolic function.", 62.0, 0),
        ("The ejection fraction is severely reduced EF.", None, 1),
        ("No echo performed this visit.", None, None),
    ]
    failures = 0
    for text, expected_numeric, expected_binary in cases:
        r = extract_lvef(text)
        ok = r.lvef_numeric == expected_numeric and r.lvef_binary_40 == expected_binary
        status = "OK" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"[{status}] {text!r} -> numeric={r.lvef_numeric}, binary_40={r.lvef_binary_40}")
    if failures:
        raise SystemExit(f"{failures} selftest case(s) failed")
    print("all selftest cases passed")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="run built-in regex tests and exit")
    sub = parser.add_subparsers(dest="command")

    p_extract = sub.add_parser("extract", help="extract LVEF from a notes CSV")
    p_extract.add_argument("--notes-csv", type=Path, required=True)
    p_extract.add_argument("--text-col", default="text")
    p_extract.add_argument("--id-col", default="note_id")
    p_extract.add_argument("--out", type=Path, required=True)
    p_extract.set_defaults(func=cmd_extract)

    p_match = sub.add_parser("match", help="pair ECG rows with nearest-in-time LVEF")
    p_match.add_argument("--ecg-csv", type=Path, required=True)
    p_match.add_argument("--lvef-csv", type=Path, required=True, help="output of `extract`")
    p_match.add_argument("--max-days", type=int, default=30)
    p_match.add_argument("--out", type=Path, required=True)
    p_match.set_defaults(func=cmd_match)

    p_sample = sub.add_parser("sample-qc", help="build a stratified sample for manual review")
    p_sample.add_argument("--matched-csv", type=Path, required=True, help="output of `match`")
    p_sample.add_argument("--n-per-bin", type=int, default=50)
    p_sample.add_argument("--seed", type=int, default=0)
    p_sample.add_argument("--out", type=Path, required=True)
    p_sample.set_defaults(func=cmd_sample_qc)

    p_score = sub.add_parser("score-qc", help="score agreement after manual_lvef is filled in")
    p_score.add_argument("--qc-csv", type=Path, required=True, help="sample-qc output with manual_lvef filled")
    p_score.set_defaults(func=cmd_score_qc)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        return
    if not getattr(args, "command", None):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
