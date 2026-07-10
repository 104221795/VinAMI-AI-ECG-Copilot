from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st

DISCLAIMER = "Research-use only. Not clinically validated. Not a substitute for physician diagnosis."


def show_disclaimer() -> None:
    st.warning(DISCLAIMER)


def read_csv_if_exists(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception as exc:
        st.warning(f"Could not read {path}: {exc}")
        return None


def display_metric_csv(path: Path, title: str) -> None:
    st.subheader(title)
    df = read_csv_if_exists(path)
    if df is None:
        st.info(f"Missing optional artifact: `{path}`")
        return
    st.dataframe(df, width="stretch")


def list_images(report_dir: Path, patterns: Iterable[str]) -> list[Path]:
    images: list[Path] = []
    for pattern in patterns:
        images.extend(sorted(report_dir.glob(pattern)))
    return sorted(set(images))


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def build_markdown_report(title: str, prediction_df: pd.DataFrame | None, image_name: str | None, gradcam_path: Path | None) -> str:
    lines = [
        f"# {title}",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"**Disclaimer:** {DISCLAIMER}",
        "",
        f"Input image: `{image_name or 'N/A'}`",
        "",
    ]
    if prediction_df is not None:
        lines.append("## Prediction Table")
        lines.append("")
        lines.append(prediction_df.to_markdown(index=False))
        lines.append("")
    if gradcam_path:
        lines.append("## Grad-CAM Explanation")
        lines.append("")
        lines.append(f"Grad-CAM image: `{gradcam_path}`")
        lines.append("")
    return "\n".join(lines)


def save_markdown_report(path: Path, title: str, prediction_df: pd.DataFrame | None, image_name: str | None, gradcam_path: Path | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = build_markdown_report(title, prediction_df, image_name, gradcam_path)
    path.write_text(content, encoding="utf-8")
