"""Generate 12-lead time-frequency grid images from PTB-XL.

This writes a new image manifest:
    outdir/manifest_images.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pywt
import scipy.signal
import wfdb
from tqdm import tqdm


LEADS = ["I", "II", "III", "AVR", "AVL", "AVF", "V1", "V2", "V3", "V4", "V5", "V6"]
LABELS = ["NORM", "MI", "STTC", "CD", "HYP"]


def normalize_signal(signal: np.ndarray) -> np.ndarray:
    signal = signal.astype(np.float32)
    signal = signal - np.nanmean(signal)
    std = np.nanstd(signal)
    if std > 0:
        signal = signal / std
    return signal


def bandpass(signal: np.ndarray, fs: int) -> np.ndarray:
    high = min(40.0, fs / 2 - 1.0)
    sos = scipy.signal.butter(4, [0.5, high], btype="bandpass", fs=fs, output="sos")
    return scipy.signal.sosfiltfilt(sos, signal)


def cwt_image(signal: np.ndarray, fs: int, bins: int = 96) -> np.ndarray:
    frequencies = np.linspace(1, min(45, fs / 2 - 1), bins)
    wavelet = "morl"
    scales = pywt.central_frequency(wavelet) * fs / frequencies
    coeffs, _ = pywt.cwt(signal, scales, wavelet, sampling_period=1 / fs)
    image = np.log1p(np.abs(coeffs))
    return image


def stft_image(signal: np.ndarray, fs: int) -> np.ndarray:
    freqs, _, spectrum = scipy.signal.spectrogram(
        signal,
        fs=fs,
        window="hann",
        nperseg=min(128, len(signal)),
        noverlap=min(64, max(0, len(signal) // 4)),
        mode="magnitude",
    )
    keep = freqs <= min(45, fs / 2)
    return 20 * np.log10(spectrum[keep] + 1e-8)


def render_grid(signals: np.ndarray, fs: int, representation: str, output_path: Path) -> None:
    fig, axes = plt.subplots(4, 3, figsize=(6, 8), dpi=120)
    for idx, ax in enumerate(axes.flat):
        ecg = normalize_signal(bandpass(signals[:, idx], fs))
        if representation == "cwt":
            image = cwt_image(ecg, fs)
        elif representation == "stft":
            image = stft_image(ecg, fs)
        else:
            raise ValueError(f"Unsupported representation: {representation}")
        ax.imshow(image, aspect="auto", origin="lower", cmap="magma")
        ax.set_title(LEADS[idx], fontsize=7)
        ax.axis("off")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout(pad=0.2)
    plt.savefig(output_path, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def read_record(ptbxl_root: Path, row: pd.Series, sampling: str) -> tuple[np.ndarray, int]:
    filename_col = "filename_hr" if sampling == "500" else "filename_lr"
    record_base = ptbxl_root / row[filename_col]
    signals, fields = wfdb.rdsamp(str(record_base))
    return signals, int(fields["fs"])


def balanced_limit(manifest: pd.DataFrame, limit: int | None) -> pd.DataFrame:
    if not limit:
        return manifest
    # Keep the experiment quick while preserving all official splits.
    chunks = []
    per_split = max(1, limit // 3)
    for split in ["train", "val", "test"]:
        frame = manifest[manifest["split"] == split]
        chunks.append(frame.sample(min(len(frame), per_split), random_state=7))
    return pd.concat(chunks).sort_values(["split", "ecg_id"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ptbxl-root", type=Path, default=Path("data/ptb-xl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/ptbxl_superclass_manifest.csv"))
    parser.add_argument("--outdir", type=Path, default=Path("data/ptbxl_images_cwt"))
    parser.add_argument("--representation", choices=["cwt", "stft"], default="cwt")
    parser.add_argument("--sampling", choices=["100", "500"], default="100")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    manifest = pd.read_csv(args.manifest)
    manifest = balanced_limit(manifest, args.limit)

    image_rows = []
    for _, row in tqdm(manifest.iterrows(), total=len(manifest)):
        signals, fs = read_record(args.ptbxl_root, row, args.sampling)
        rel_path = Path(row["split"]) / f"{int(row['ecg_id']):05d}_{args.representation}.png"
        image_path = args.outdir / rel_path
        render_grid(signals, fs, args.representation, image_path)

        output = row.to_dict()
        output["image_path"] = str(image_path)
        image_rows.append(output)

    image_manifest = pd.DataFrame(image_rows)
    manifest_path = args.outdir / "manifest_images.csv"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    image_manifest.to_csv(manifest_path, index=False)
    print(f"Saved image manifest: {manifest_path}")


if __name__ == "__main__":
    main()

