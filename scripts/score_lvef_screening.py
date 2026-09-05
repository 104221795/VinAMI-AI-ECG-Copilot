"""Binary-screening + calibration metrics for the LVEF<=40% model
(proposal section 12 "Binary screening head"/"Reliability", Experiment 6).

src/train_signal_1d.py's own `score()` already reports macro/per-label
AUROC/AUPRC/F1 from a --probabilities npz, which covers most of what a
generic multi-label ACS run needs. It does NOT report sensitivity/
specificity at a clinical threshold, false-negative counts, or calibration
(Brier score / Expected Calibration Error) -- exactly the numbers the LVEF
proposal cares about most, since missing a true low-EF patient (false
negative) is the clinically costly error, not overall accuracy. This script
adds those on top of a probabilities npz produced by:

    python3 src/train_signal_1d.py --cache data/lvef_signal_cache \\
        --labels lvef_binary_40 --probabilities probs_lvef.npz ...

Usage:
    python3 scripts/score_lvef_screening.py --probabilities probs_lvef.npz --label lvef_binary_40
    python3 scripts/score_lvef_screening.py --selftest
"""

from __future__ import annotations

import argparse

import numpy as np
from sklearn.metrics import roc_curve


def sensitivity_specificity(y_true: np.ndarray, y_prob: np.ndarray, threshold: float) -> dict:
    y_pred = (y_prob >= threshold).astype(int)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    sensitivity = tp / (tp + fn) if (tp + fn) else float("nan")
    specificity = tn / (tn + fp) if (tn + fp) else float("nan")
    return {
        "threshold": threshold,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "false_negative_rate": fn / (tp + fn) if (tp + fn) else float("nan"),
    }


def youden_optimal_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Threshold maximising sensitivity + specificity - 1 (Youden's J).
    Reported alongside the fixed 0.5 threshold -- proposal section 12 wants
    both a standard operating point and a clinically-tuned one."""
    fpr, tpr, thresholds = roc_curve(y_true, y_prob)
    j = tpr - fpr
    return float(thresholds[int(np.argmax(j))])


def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    return float(np.mean((y_prob - y_true) ** 2))


def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> tuple[float, list[dict]]:
    """Standard equal-width-bin ECE: weighted mean |confidence - accuracy| per bin."""
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_ids = np.clip(np.digitize(y_prob, bin_edges[1:-1]), 0, n_bins - 1)
    ece = 0.0
    bins = []
    for b in range(n_bins):
        mask = bin_ids == b
        count = int(mask.sum())
        if count == 0:
            bins.append({"bin": f"{bin_edges[b]:.1f}-{bin_edges[b+1]:.1f}", "count": 0, "confidence": None, "accuracy": None})
            continue
        confidence = float(y_prob[mask].mean())
        accuracy = float(y_true[mask].mean())
        ece += (count / len(y_true)) * abs(confidence - accuracy)
        bins.append({
            "bin": f"{bin_edges[b]:.1f}-{bin_edges[b+1]:.1f}",
            "count": count,
            "confidence": confidence,
            "accuracy": accuracy,
        })
    return float(ece), bins


def full_report(y_true: np.ndarray, y_prob: np.ndarray) -> dict:
    youden = youden_optimal_threshold(y_true, y_prob)
    ece, bins = expected_calibration_error(y_true, y_prob)
    return {
        "n": len(y_true),
        "n_positive": int(y_true.sum()),
        "at_threshold_0.5": sensitivity_specificity(y_true, y_prob, 0.5),
        "at_youden_optimal": sensitivity_specificity(y_true, y_prob, youden),
        "brier_score": brier_score(y_true, y_prob),
        "expected_calibration_error": ece,
        "calibration_bins": bins,
    }


def cmd_score(args: argparse.Namespace) -> None:
    data = np.load(args.probabilities, allow_pickle=True)
    labels = list(data["labels"])
    idx = labels.index(args.label)
    y_test = data["y_test"][:, idx]
    prob_test = data["prob_test"][:, idx]
    report = full_report(y_test, prob_test)
    for key, value in report.items():
        if key == "calibration_bins":
            print("calibration_bins:")
            for row in value:
                print(f"  {row}")
        else:
            print(f"{key}: {value}")
    if report["at_threshold_0.5"]["false_negative_rate"] > 0.2:
        print(
            "WARNING: false-negative rate > 20% at threshold 0.5 -- per proposal section 12, "
            "this is the clinically costly error (missed low-EF patient). Consider the Youden "
            "threshold instead, or revisit class-imbalance handling (section 10) before reporting."
        )


def _selftest() -> None:
    rng = np.random.default_rng(0)
    n = 2000
    y_true = (rng.random(n) < 0.15).astype(int)  # ~15% prevalence, similar to low-EF in a general population
    # a somewhat-informative, imperfectly-calibrated classifier
    y_prob = np.clip(0.1 + 0.6 * y_true + rng.normal(0, 0.15, n), 0.001, 0.999)

    report = full_report(y_true, y_prob)
    assert 0.0 <= report["brier_score"] <= 1.0
    assert 0.0 <= report["expected_calibration_error"] <= 1.0
    assert 0.0 <= report["at_threshold_0.5"]["sensitivity"] <= 1.0
    assert 0.0 <= report["at_threshold_0.5"]["specificity"] <= 1.0
    total = (
        report["at_threshold_0.5"]["true_positive"]
        + report["at_threshold_0.5"]["true_negative"]
        + report["at_threshold_0.5"]["false_positive"]
        + report["at_threshold_0.5"]["false_negative"]
    )
    assert total == n
    print(f"n={n}, brier={report['brier_score']:.4f}, ece={report['expected_calibration_error']:.4f}")
    print(f"threshold=0.5: {report['at_threshold_0.5']}")
    print(f"youden threshold={report['at_youden_optimal']['threshold']:.3f}: {report['at_youden_optimal']}")
    print("all selftest assertions passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--probabilities", type=str, default=None)
    parser.add_argument("--label", type=str, default="lvef_binary_40")
    args = parser.parse_args()

    if args.selftest:
        _selftest()
        return
    if not args.probabilities:
        raise SystemExit("--probabilities is required (or use --selftest)")
    cmd_score(args)


if __name__ == "__main__":
    main()
