"""Convert EchoNext-Mini (PhysioNet, restricted access) into signals.f16.npy
+ index.csv for the *unmodified* src/train_signal_1d.py.

See Research/VinStroke_ECG_LVEF_Research_Proposal.md section 8.1 for why this
dataset is now the priority-1 source: it ships a ready-made structured label
(`lvef_lte_45_flag`) from the source study, so unlike the MIMIC-IV-Note route
in build_lvef_label_extraction.py, there is NO NLP/regex extraction step
here -- this script only reshapes/resamples/normalises and writes the label.

Expected EchoNext-Mini layout (VERIFY against the real download once the
Restricted Health Data License DUA is signed -- not confirmed locally):
    waveforms: .npy, shape (N, 1, 2500, 12) -- 10 s @ 250 Hz, 12 leads
    metadata:  .csv, one row per waveform in the SAME order, containing at
               least a patient-id column and `lvef_lte_45_flag`

IMPORTANT: the output label column is `lvef_binary_45`, NOT `lvef_binary_40`
-- EchoNext's own cutoff is LVEF <= 45% ("moderately reduced systolic
function"), a different clinical question than the HFrEF <= 40% threshold
the rest of this proposal is built around (section 7.2-7.3, and
cache_lvef_signals.py's `lvef_binary_40`). Do not merge the two label
columns or the two training runs answer different questions without anyone
noticing.

Resampling 250 Hz -> 500 Hz (2500 -> 5000 samples): the Conv1d/
AdaptiveAvgPool1d backbones in src/models_1d.py are shape-agnostic, so this
is not required for the model to run, but a fixed-width kernel covers a
different real-world time window at a different sampling rate (e.g. a
15-tap kernel spans 60 ms at 250 Hz vs 30 ms at 500 Hz). Resampling keeps
kernel receptive fields physiologically comparable to the PTB-XL/ACS-
pretrained checkpoints this is meant to transfer-learn from.

Usage:
    python3 scripts/cache_echonext_signals.py --waveforms waveforms.npy --metadata metadata.csv
    python3 scripts/cache_echonext_signals.py --selftest   # resample/normalise math only, no real data needed
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.signal


def resample_to(signals: np.ndarray, target_length: int) -> np.ndarray:
    """(T, 12) -> (target_length, 12) via FFT-based polyphase resampling."""
    if signals.shape[0] == target_length:
        return signals
    return scipy.signal.resample(signals, target_length, axis=0)


def normalise(signals: np.ndarray) -> np.ndarray:
    mean = signals.mean(axis=0, keepdims=True)
    std = signals.std(axis=0, keepdims=True)
    return (signals - mean) / np.maximum(std, 1e-6)


def cmd_convert(args: argparse.Namespace) -> None:
    waveforms = np.load(args.waveforms, mmap_mode="r")
    metadata = pd.read_csv(args.metadata)
    if len(waveforms) != len(metadata):
        raise SystemExit(
            f"waveforms ({len(waveforms)}) va metadata ({len(metadata)}) khong khop so hang - "
            "gia dinh 've thu tu hang giong nhau giua hai file co the sai, kiem tra lai truoc khi tiep tuc."
        )
    if args.limit:
        waveforms = waveforms[: args.limit]
        metadata = metadata.iloc[: args.limit].reset_index(drop=True)

    before = len(metadata)
    keep = metadata[args.label_col].notna().to_numpy()
    metadata = metadata[keep].reset_index(drop=True)
    waveforms = waveforms[keep]
    print(f"{len(metadata)}/{before} ban ghi co {args.label_col}")

    args.outdir.mkdir(parents=True, exist_ok=True)
    signal_path = args.outdir / "signals.f16.npy"
    memmap = np.lib.format.open_memmap(
        signal_path, mode="w+", dtype=np.float16, shape=(len(metadata), 12, args.target_length)
    )
    for i in range(len(metadata)):
        raw = np.asarray(waveforms[i, 0], dtype=np.float32)  # (2500, 12) after dropping the channel-1 axis
        prepared = normalise(resample_to(raw, args.target_length))
        memmap[i] = prepared.T.astype(np.float16)
        if (i + 1) % 5000 == 0:
            print(f"  {i + 1}/{len(metadata)}")
    memmap.flush()
    del memmap

    index = pd.DataFrame(
        {
            "Patient_id": metadata[args.id_col],
            "record_id": metadata[args.record_id_col] if args.record_id_col in metadata.columns else np.arange(len(metadata)),
            "cache_index": np.arange(len(metadata)),
            "lvef_binary_45": metadata[args.label_col].astype(int),
        }
    )
    index.to_csv(args.outdir / "index.csv", index=False)
    print(f"Da ghi {len(index)} ban ghi vao {args.outdir}")
    print(f"lvef_binary_45 phan bo: {index['lvef_binary_45'].value_counts().to_dict()}")


def _selftest() -> None:
    rng = np.random.default_rng(0)
    raw = rng.normal(0, 1, (2500, 12)).astype(np.float32)

    same_length = resample_to(raw, 2500)
    assert same_length.shape == (2500, 12)
    assert np.allclose(same_length, raw)

    upsampled = resample_to(raw, 5000)
    assert upsampled.shape == (5000, 12), f"expected (5000, 12), got {upsampled.shape}"

    normalised = normalise(upsampled)
    assert normalised.shape == upsampled.shape
    means = normalised.mean(axis=0)
    stds = normalised.std(axis=0)
    assert np.allclose(means, 0.0, atol=1e-5), f"per-lead mean should be ~0, got {means}"
    assert np.allclose(stds, 1.0, atol=1e-2), f"per-lead std should be ~1, got {stds}"

    print("resample_to: identity + 250Hz->500Hz upsampling shape OK")
    print("normalise: per-lead zero-mean/unit-variance OK")
    print("all selftest assertions passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--waveforms", type=Path, help="EchoNext-Mini waveform .npy, shape (N, 1, 2500, 12)")
    parser.add_argument("--metadata", type=Path, help="EchoNext-Mini metadata CSV, same row order as waveforms")
    parser.add_argument("--id-col", default="patient_id", help="Patient-grouping column (VERIFY against real file)")
    parser.add_argument("--record-id-col", default="ecg_id")
    parser.add_argument("--label-col", default="lvef_lte_45_flag", help="Source label column (VERIFY against real file)")
    parser.add_argument("--outdir", type=Path, default=Path("data/echonext_signal_cache"))
    parser.add_argument("--target-length", type=int, default=5000, help="500 Hz x 10s, matches PTB-XL/ACS caches")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if args.selftest:
        _selftest()
        return
    if not args.waveforms or not args.metadata:
        raise SystemExit("--waveforms and --metadata are required (or use --selftest)")
    cmd_convert(args)


if __name__ == "__main__":
    main()
