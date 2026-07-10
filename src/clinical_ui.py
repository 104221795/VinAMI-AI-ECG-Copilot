from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st


LABEL_DETAILS = {
    "NORM": ("Normal ECG", "ECGs grouped under the PTB-XL normal diagnostic superclass."),
    "MI": ("Myocardial infarction", "ECG patterns grouped under the PTB-XL myocardial infarction superclass."),
    "STTC": ("ST/T change", "Repolarization findings grouped under ST-segment or T-wave change."),
    "CD": ("Conduction disturbance", "Electrical conduction findings grouped under the PTB-XL CD superclass."),
    "HYP": ("Hypertrophy", "ECG patterns grouped under the cardiac hypertrophy superclass."),
}


def apply_clinical_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --vm-teal: #007f86;
            --vm-teal-dark: #075d63;
            --vm-teal-soft: #eaf6f6;
            --vm-ink: #18363a;
            --vm-muted: #60767a;
            --vm-line: #dbe6e7;
            --vm-bg: #f5f8f8;
            --vm-danger: #b33a3a;
            --vm-warning: #9a6400;
        }
        html, body, [class*="css"] {
            font-family: Inter, "Segoe UI", Arial, sans-serif;
            color: var(--vm-ink);
        }
        .stApp { background: var(--vm-bg); }
        [data-testid="stHeader"] { background: rgba(245, 248, 248, 0.96); }
        [data-testid="stToolbar"] { right: 1rem; }
        .block-container {
            max-width: 1480px;
            padding-top: 1.25rem;
            padding-bottom: 3rem;
        }
        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid var(--vm-line);
        }
        [data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }
        h1, h2, h3 { color: var(--vm-ink); letter-spacing: 0; }
        h1 { font-size: 2rem; line-height: 1.18; }
        h2 { font-size: 1.35rem; }
        h3 { font-size: 1.05rem; }
        p, li { color: var(--vm-muted); }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff;
            border-color: var(--vm-line) !important;
            border-radius: 6px !important;
        }
        div.stButton > button, div.stDownloadButton > button {
            border-radius: 5px;
            min-height: 2.65rem;
            font-weight: 650;
            border-color: var(--vm-teal);
        }
        div.stButton > button[kind="primary"], div.stDownloadButton > button[kind="primary"] {
            background: var(--vm-teal);
            color: #ffffff;
        }
        div.stButton > button:hover, div.stDownloadButton > button:hover {
            border-color: var(--vm-teal-dark);
            color: var(--vm-teal-dark);
        }
        div.stButton > button[kind="primary"]:hover,
        div.stDownloadButton > button[kind="primary"]:hover {
            background: var(--vm-teal-dark);
            color: #ffffff;
        }
        div[data-baseweb="select"] > div,
        [data-testid="stFileUploaderDropzone"] {
            border-radius: 5px;
            border-color: var(--vm-line);
            background: #ffffff;
        }
        [data-testid="stDataFrame"] { border: 1px solid var(--vm-line); border-radius: 5px; }
        [data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid var(--vm-line);
            border-top: 3px solid var(--vm-teal);
            padding: 0.85rem 1rem;
            border-radius: 5px;
        }
        [data-testid="stMetricValue"] { font-size: 1.55rem; color: var(--vm-ink); }
        [data-testid="stImage"] img { border-radius: 4px; }
        .vm-brand {
            display: flex;
            align-items: center;
            gap: .72rem;
            margin-bottom: 1.2rem;
        }
        .vm-brand-mark {
            width: 34px;
            height: 34px;
            display: grid;
            place-items: center;
            border: 2px solid var(--vm-teal);
            color: var(--vm-teal);
            font-size: 1.35rem;
            font-weight: 700;
            border-radius: 5px;
        }
        .vm-brand-name { font-size: 1.08rem; font-weight: 750; color: var(--vm-ink); line-height: 1.1; }
        .vm-brand-sub { font-size: .72rem; color: var(--vm-muted); margin-top: .18rem; }
        .vm-hero {
            background: #ffffff;
            border: 1px solid var(--vm-line);
            border-left: 5px solid var(--vm-teal);
            border-radius: 6px;
            padding: 1.25rem 1.4rem;
            margin: .2rem 0 1rem;
        }
        .vm-eyebrow {
            color: var(--vm-teal-dark);
            font-size: .74rem;
            text-transform: uppercase;
            font-weight: 750;
            letter-spacing: .06em;
            margin-bottom: .35rem;
        }
        .vm-hero h1 { margin: 0; font-size: 1.8rem; }
        .vm-hero p { margin: .45rem 0 0; max-width: 920px; }
        .vm-status-row { display: flex; flex-wrap: wrap; gap: .45rem; margin-top: .85rem; }
        .vm-pill {
            display: inline-flex;
            align-items: center;
            border: 1px solid #b8d9da;
            background: var(--vm-teal-soft);
            color: var(--vm-teal-dark);
            padding: .28rem .55rem;
            border-radius: 999px;
            font-size: .74rem;
            font-weight: 650;
        }
        .vm-notice {
            border: 1px solid #ead9ab;
            background: #fffaf0;
            color: #70531a;
            border-radius: 5px;
            padding: .68rem .85rem;
            font-size: .82rem;
            margin-bottom: 1rem;
        }
        .vm-steps {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            background: #ffffff;
            border: 1px solid var(--vm-line);
            border-radius: 6px;
            margin-bottom: 1rem;
            overflow: hidden;
        }
        .vm-step { padding: .72rem .85rem; border-right: 1px solid var(--vm-line); }
        .vm-step:last-child { border-right: 0; }
        .vm-step-num { font-size: .7rem; font-weight: 750; color: var(--vm-teal); text-transform: uppercase; }
        .vm-step-name { color: var(--vm-ink); font-weight: 650; font-size: .84rem; margin-top: .1rem; }
        .vm-section-title { margin: 1rem 0 .55rem; }
        .vm-section-title h2 { margin: 0; font-size: 1.28rem; }
        .vm-section-title p { margin: .25rem 0 0; font-size: .85rem; }
        .vm-footer-note { color: var(--vm-muted); font-size: .72rem; line-height: 1.45; }
        @media (max-width: 900px) {
            .block-container { padding: .8rem .8rem 2rem; }
            .vm-steps { grid-template-columns: repeat(2, 1fr); }
            .vm-step:nth-child(2) { border-right: 0; }
            .vm-step:nth-child(-n+2) { border-bottom: 1px solid var(--vm-line); }
        }
        @media (max-width: 560px) {
            .vm-hero { padding: 1rem; }
            .vm-hero h1 { font-size: 1.45rem; }
            .vm-steps { grid-template-columns: 1fr; }
            .vm-step { border-right: 0; border-bottom: 1px solid var(--vm-line); }
            .vm-step:last-child { border-bottom: 0; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_brand() -> None:
    st.markdown(
        """
        <div class="vm-brand">
          <div class="vm-brand-mark">V</div>
          <div><div class="vm-brand-name">VinStroke ECG</div><div class="vm-brand-sub">Clinical research workspace</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, description: str, eyebrow: str = "AI-assisted ECG interpretation") -> None:
    st.markdown(
        f"""
        <div class="vm-hero">
          <div class="vm-eyebrow">{escape(eyebrow)}</div>
          <h1>{escape(title)}</h1>
          <p>{escape(description)}</p>
          <div class="vm-status-row">
            <span class="vm-pill">PTB-XL</span>
            <span class="vm-pill">12-lead CWT</span>
            <span class="vm-pill">Multi-label</span>
            <span class="vm-pill">Research prototype</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def research_notice() -> None:
    st.markdown(
        """
        <div class="vm-notice"><strong>Research use only.</strong> This system is not clinically validated and must not be used as a diagnosis, triage decision, or substitute for review by a qualified clinician.</div>
        """,
        unsafe_allow_html=True,
    )


def workflow_steps() -> None:
    steps = [
        ("Step 1", "Select ECG input"),
        ("Step 2", "Inspect raw and CWT"),
        ("Step 3", "Review model output"),
        ("Step 4", "Explain and export"),
    ]
    body = "".join(
        f'<div class="vm-step"><div class="vm-step-num">{number}</div><div class="vm-step-name">{name}</div></div>'
        for number, name in steps
    )
    st.markdown(f'<div class="vm-steps">{body}</div>', unsafe_allow_html=True)


def section_title(title: str, description: str) -> None:
    st.markdown(
        f'<div class="vm-section-title"><h2>{escape(title)}</h2><p>{escape(description)}</p></div>',
        unsafe_allow_html=True,
    )


def rank_prediction_results(table: pd.DataFrame, quality_by_label: dict[str, dict[str, float]] | None = None) -> pd.DataFrame:
    """Create one explicit, clinician-oriented ordering for the five independent heads."""
    quality_by_label = quality_by_label or {}
    ranked = table.copy()
    ranked["diagnostic_superclass"] = ranked["label"].map(lambda label: LABEL_DETAILS.get(str(label), (str(label), ""))[0])
    ranked["is_abnormal"] = ranked["label"] != "NORM"
    ranked["is_positive"] = ranked["decision"] == "Screen positive"
    ranked["is_near_threshold"] = ranked["review_flag"] == "Near threshold - review"

    def state(row: pd.Series) -> str:
        if row["is_abnormal"] and row["is_positive"]:
            return "Screen positive - review waveform"
        if row["is_near_threshold"]:
            return "Near threshold - review"
        if row["label"] == "NORM" and row["is_positive"]:
            return "Normal-pattern support"
        return "Below threshold"

    def bucket(row: pd.Series) -> int:
        if row["is_abnormal"] and row["is_positive"]:
            return 0
        if row["is_near_threshold"]:
            return 1
        if row["label"] == "NORM" and row["is_positive"]:
            return 2
        return 3

    def evidence(label: str) -> str:
        f1 = quality_by_label.get(str(label), {}).get("f1")
        if f1 is None:
            return "No held-out metric"
        if f1 >= 0.75:
            return f"Stronger evidence (test F1 {f1:.2f})"
        if f1 >= 0.60:
            return f"Moderate evidence (test F1 {f1:.2f})"
        return f"Limited evidence (test F1 {f1:.2f})"

    ranked["review_state"] = ranked.apply(state, axis=1)
    ranked["priority_bucket"] = ranked.apply(bucket, axis=1)
    ranked["validation_evidence"] = ranked["label"].map(evidence)
    ranked["abs_margin"] = ranked["threshold_margin"].abs()
    ranked["within_bucket_order"] = ranked["probability"]
    # A near-threshold label is ordered by closeness; all other groups are ordered by score.
    ranked.loc[ranked["is_near_threshold"], "within_bucket_order"] = 1 - ranked.loc[
        ranked["is_near_threshold"], "abs_margin"
    ]
    ranked = ranked.sort_values(
        ["priority_bucket", "within_bucket_order"],
        ascending=[True, False],
        kind="stable",
    ).reset_index(drop=True)
    ranked.insert(0, "rank", range(1, len(ranked) + 1))
    return ranked


def render_ranked_predictions(ranked: pd.DataFrame) -> None:
    abnormal_positive = ranked.loc[
        (ranked["is_abnormal"]) & (ranked["is_positive"]), "label"
    ].astype(str).tolist()
    near_threshold = ranked.loc[ranked["is_near_threshold"], "label"].astype(str).tolist()
    norm_support = bool(((ranked["label"] == "NORM") & (ranked["is_positive"])).any())

    if abnormal_positive:
        st.warning(
            f"Review priority: {', '.join(abnormal_positive)} crossed its screening threshold. "
            "Confirm against the original 12-lead waveform."
        )
    elif near_threshold:
        st.warning(f"No abnormal label crossed threshold, but {', '.join(near_threshold)} is near its decision boundary.")
    elif norm_support:
        st.success("No abnormal superclass crossed its screening threshold; the NORM head supports a normal-pattern interpretation.")
    else:
        st.info("No label crossed its screening threshold. This does not establish a normal ECG or exclude disease.")

    display = ranked.copy()
    display["model_score"] = display["probability"].map(lambda value: f"{float(value) * 100:.1f}%")
    display["threshold"] = display["threshold"].map(lambda value: f"{float(value) * 100:.0f}%")
    display["margin"] = display["threshold_margin"].map(lambda value: f"{float(value) * 100:+.1f}%")
    st.dataframe(
        display[
            [
                "rank",
                "label",
                "diagnostic_superclass",
                "model_score",
                "threshold",
                "margin",
                "review_state",
                "validation_evidence",
            ]
        ],
        column_config={
            "rank": st.column_config.NumberColumn("Priority", format="%d"),
            "label": "Code",
            "diagnostic_superclass": "PTB-XL superclass",
            "model_score": "Model score",
            "threshold": "Threshold",
            "margin": "Score - threshold",
            "review_state": "Review state",
            "validation_evidence": "Held-out evidence",
        },
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "Order: abnormal screen-positive findings, near-threshold findings, normal-pattern support, then remaining below-threshold outputs. "
        "All five heads are independent, so a conflicting NORM and abnormal result requires review."
    )


def label_reference() -> None:
    rows = [
        {"Code": code, "Diagnostic superclass": name, "Interpretation scope": detail}
        for code, (name, detail) in LABEL_DETAILS.items()
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
