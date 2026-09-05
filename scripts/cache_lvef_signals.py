"""Cache ECG-LVEF matched records as one float16 memmap for src/train_signal_1d.py.

This mirrors scripts/cache_acs_signals.py exactly (same bandpass/denoise/
normalise/fit_length pipeline, same output layout), so a LVEF cache trains
with the *unmodified* train_signal_1d.py:

    python3 src/train_signal_1d.py --cache data/lvef_signal_cache \\
        --labels lvef_binary_40 --model xresnet1d101 \\
        --init-from-checkpoint models/ptbxl_xresnet1d101.pt \\
        --output models/lvef_xresnet1d101.pt \\
        --metrics-json metrics_lvef_xresnet1d101.json \\
        --probabilities probs_lvef_xresnet1d101.npz

Reusing the same preprocessing as the PTB-XL/ACS caches matters here: the
whole point of --init-from-checkpoint transfer learning (proposal section
9.3/Experiment 4) is that the backbone already expects signals normalised
this exact way. A different bandpass/normalisation would silently defeat
the transfer-learning ablation, not just look different.

Input: the output of `build_lvef_label_extraction.py match` (see that
script's docstring for the matched-CSV schema and Phase 0 caveats about
MIMIC-IV-ECG/ECHO column names not being locally verified yet). This script
additionally needs a column giving the WFDB record path per ECG -- for
MIMIC-IV-ECG that is documented as `path` in record_list.csv (relative to
the files/ root), but VERIFY against the real export once access exists;
override with --record-col if it differs.

Output index.csv intentionally names the patient column `Patient_id`
(MIMIC/ACS convention differs: `subject_id`) so that train_signal_1d.py's
hardcoded patient-grouped split (`assign_patient_splits`, the leak check)
works unmodified -- see that file's `index.groupby("Patient_id")`.

Rows whose `lvef_binary_40` is missing (excluded "mild reduction" bucket,
or extraction found nothing) are dropped before caching: there is nothing
for the binary head to train on for those rows (see proposal section 7.3).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pywt
import scipy.signal
import wfdb


def bandpass(signals: np.ndarray, fs: float) -> np.ndarray:
    """0.5-40 Hz: drops baseline wander and mains/EMG noise while keeping the
    QRS/ST morphology an LVEF signal depends on. Identical to cache_acs_signals.py
    and cache_ptbxl_signals.py so the transfer-learning backbone sees the same
    input distribution it was pretrained on."""
    high = min(40.0, fs / 2 - 1.0)
    sos = scipy.signal.butter(4, [0.5, high], btype="bandpass", fs=fs, output="sos")
    return scipy.signal.sosfiltfilt(sos, signals, axis=0)


def wavelet_denoise(signals: np.ndarray, wavelet: str = "db6", level: int = 4) -> np.ndarray:
    """VisuShrink wavelet-threshold denoising, per lead. Copied verbatim from
    cache_acs_signals.py -- keep the two in sync if this changes there."""
    max_level = pywt.dwt_max_level(signals.shape[0], pywt.Wavelet(wavelet).dec_len)
    denoised = np.empty_like(signals, dtype=np.float64)
    for lead in range(signals.shape[1]):
        coeffs = pywt.wavedec(signals[:, lead], wavelet, level=min(level, max_level))
        sigma = np.median(np.abs(coeffs[-1])) / 0.6745
        if sigma > 0:
            threshold = sigma * np.sqrt(2 * np.log(signals.shape[0]))
            coeffs[1:] = [pywt.threshold(detail, threshold, mode="soft") for detail in coeffs[1:]]
        denoised[:, lead] = pywt.waverec(coeffs, wavelet)[: signals.shape[0]]
    return denoised


def normalise(signals: np.ndarray) -> np.ndarray:
    mean = signals.mean(axis=0, keepdims=True)
    std = signals.std(axis=0, keepdims=True)
    return (signals - mean) / np.maximum(std, 1e-6)


def fit_length(signals: np.ndarray, length: int) -> np.ndarray:
    have = signals.shape[0]
    if have == length:
        return signals
    if have > length:
        start = (have - length) // 2
        return signals[start : start + length]
    padded = np.zeros((length, signals.shape[1]), dtype=signals.dtype)
    start = (length - have) // 2
    padded[start : start + have] = signals
    return padded


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matched-csv", type=Path, required=True, help="Output of build_lvef_label_extraction.py match")
    parser.add_argument("--signal-dir", type=Path, required=True, help="Root directory WFDB record paths are relative to")
    parser.add_argument("--record-col", default="path", help="Column giving the WFDB record path, relative to --signal-dir")
    parser.add_argument("--subject-col", default="subject_id")
    parser.add_argument("--outdir", type=Path, default=Path("data/lvef_signal_cache"))
    parser.add_argument("--length", type=int, default=5000, help="Samples per record (10 s at 500 Hz, matches PTB-XL/ACS caches)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--denoise", action="store_true")
    parser.add_argument("--skip-bandpass", action="store_true", help="Raw-signal ablation baseline")
    args = parser.parse_args()

    frame = pd.read_csv(args.matched_csv)
    before = len(frame)
    frame = frame.dropna(subset=["lvef_binary_40"]).reset_index(drop=True)
    print(f"{len(frame)}/{before} ban ghi co lvef_binary_40 (da loai cac ca 'mild'/khong xac dinh)")
    if args.limit:
        frame = frame.head(args.limit).reset_index(drop=True)
    print(f"{len(frame)} ban ghi / {frame[args.subject_col].nunique()} benh nhan")

    args.outdir.mkdir(parents=True, exist_ok=True)
    signal_path = args.outdir / "signals.f16.npy"
    memmap = np.lib.format.open_memmap(
        signal_path, mode="w+", dtype=np.float16, shape=(len(frame), 12, args.length)
    )

    kept_rows = []
    failed = 0
    for position, row in enumerate(frame.to_dict("records")):
        record_rel = row[args.record_col]
        stem = str(Path(record_rel).with_suffix(""))
        try:
            signals, fields = wfdb.rdsamp(str(args.signal_dir / stem))
        except Exception as error:
            if failed < 10:
                print(f"  ! bo qua {stem}: {error}")
            failed += 1
            continue
        if signals.shape[1] < 12:
            failed += 1
            continue

        filtered = np.nan_to_num(signals[:, :12])
        if not args.skip_bandpass:
            filtered = bandpass(filtered, fields["fs"])
        if args.denoise:
            filtered = wavelet_denoise(filtered)
        prepared = normalise(fit_length(filtered, args.length))
        memmap[len(kept_rows)] = prepared.T.astype(np.float16)
        kept_rows.append(
            {
                "Patient_id": row[args.subject_col],
                "record_id": stem,
                "cache_index": len(kept_rows),
                "lvef_binary_40": int(row["lvef_binary_40"]),
                "lvef_numeric": row.get("lvef_numeric"),
                "time_delta_days": row.get("time_delta_days"),
            }
        )

        if (position + 1) % 1000 == 0:
            print(f"  {position + 1}/{len(frame)}")

    memmap.flush()
    del memmap

    if len(kept_rows) != len(frame):
        full = np.load(signal_path, mmap_mode="r")
        trimmed = np.lib.format.open_memmap(
            args.outdir / "signals.trimmed.f16.npy", mode="w+", dtype=np.float16, shape=(len(kept_rows), 12, args.length)
        )
        trimmed[:] = full[: len(kept_rows)]
        trimmed.flush()
        del trimmed, full
        (args.outdir / "signals.trimmed.f16.npy").replace(signal_path)

    pd.DataFrame(kept_rows).to_csv(args.outdir / "index.csv", index=False)
    print(f"Da ghi {len(kept_rows)} ban ghi ({failed} loi/bo qua) vao {args.outdir}")
    print(f"lvef_binary_40 phan bo: {pd.DataFrame(kept_rows)['lvef_binary_40'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
