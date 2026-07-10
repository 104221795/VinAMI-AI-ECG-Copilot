from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd
import streamlit as st
import torch
from PIL import Image

from src.clinical_ui import (
    LABEL_DETAILS,
    apply_clinical_theme,
    label_reference,
    page_header,
    rank_prediction_results,
    render_ranked_predictions,
    research_notice,
    section_title,
    sidebar_brand,
)
from src.gradcam import generate_gradcam, save_overlay
from src.model_utils import (
    choose_checkpoint,
    find_artifact_root,
    get_image_size,
    get_label_names,
    load_json,
    load_model,
    load_thresholds,
    predict_image,
    prediction_table,
)
from src.preprocessing import eval_transform, load_uploaded_image
from src.ui_utils import build_markdown_report, list_images, read_csv_if_exists, save_markdown_report, timestamp


PROJECT_ROOT = Path(__file__).resolve().parent
ARTIFACT_ROOT = find_artifact_root(PROJECT_ROOT)
REPORT_DIR = ARTIFACT_ROOT / "reports"
MANIFEST_DIR = ARTIFACT_ROOT / "manifests"
CONFIG = load_json(ARTIFACT_ROOT / "config.json")
CHECKPOINT_PATH = choose_checkpoint(ARTIFACT_ROOT)
LABELS = get_label_names(CONFIG, {})
IMAGE_SIZE = get_image_size(CONFIG, {})

st.set_page_config(page_title="VinStroke ECG | Patient Case Review", layout="wide", initial_sidebar_state="expanded")
apply_clinical_theme()


@st.cache_data
def cached_csv(path: str) -> pd.DataFrame | None:
    return read_csv_if_exists(Path(path))


@st.cache_resource(show_spinner=False)
def cached_model(checkpoint: str, config: dict, device: str):
    return load_model(Path(checkpoint), config, device)


def model_available() -> bool:
    return CHECKPOINT_PATH is not None and CHECKPOINT_PATH.exists()


def load_runtime_model():
    if not model_available():
        return None, LABELS, {}, "cpu"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, labels, checkpoint = cached_model(str(CHECKPOINT_PATH), CONFIG, device)
    return model, labels, checkpoint, device


def extract_ecg_id(path: Path) -> int | None:
    match = re.search(r"ecg[_-]?(\d+)", path.stem, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"(?:grid|probabilities)[_-](\d+)$", path.stem, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def infer_artifact_label(path: Path) -> str | None:
    upper = path.stem.upper()
    return next((label for label in [*LABELS, "AFIB"] if re.search(rf"(?:^|_){label}(?:_|$)", upper)), None)


@st.cache_data
def load_case_metadata(manifest_path: str) -> dict[int, dict]:
    path = Path(manifest_path)
    if not path.exists():
        return {}
    wanted = ["ecg_id", "patient_id", "age", "recording_date", "device", "split", "validated_by_human"]
    frame = pd.read_csv(path, usecols=lambda column: column in wanted)
    metadata: dict[int, dict] = {}
    for row in frame.itertuples(index=False):
        ecg_id = int(row.ecg_id)
        patient_id = None if pd.isna(row.patient_id) else int(row.patient_id)
        age = None if pd.isna(row.age) else int(row.age)
        date = "Unknown" if pd.isna(row.recording_date) else str(row.recording_date)[:10]
        device = "Unknown" if pd.isna(row.device) else str(row.device).strip()
        metadata[ecg_id] = {
            "patient_id": patient_id,
            "age": age,
            "recording_date": date,
            "device": device,
            "split": str(row.split),
            "human_validated": bool(row.validated_by_human),
        }
    return metadata


@st.cache_data
def build_asset_maps(report_dir: str) -> dict[str, dict]:
    root = Path(report_dir)

    def best_paths(patterns: list[str], priority) -> dict[int, str]:
        selected: dict[int, Path] = {}
        for path in list_images(root, patterns):
            ecg_id = extract_ecg_id(path)
            if ecg_id is None:
                continue
            current = selected.get(ecg_id)
            if current is None or priority(path) < priority(current):
                selected[ecg_id] = path
        return {ecg_id: str(path) for ecg_id, path in selected.items()}

    raw = best_paths(
        ["inference_raw_ecg_*.png", "raw_12lead_*.png", "spatial_12lead_*.png"],
        lambda path: 0 if path.name.startswith("inference_raw") else 1 if path.name.startswith("raw_12lead") else 2,
    )
    # Only these names are actual CWT renderings. spatial_12lead_* files are raw waveform grids.
    cwt = best_paths(["inference_cwt_grid_*.png", "ecg*_cwt_grid.png"], lambda path: 0 if path.name.startswith("inference_cwt") else 1)
    stft = best_paths(["ecg*_stft_grid.png"], lambda path: 0)

    heatmaps: dict[int, dict[str, str]] = {}
    for path in list_images(root, ["explainability_*.png", "ui_gradcam_*.png"]):
        ecg_id = extract_ecg_id(path)
        label = infer_artifact_label(path)
        if ecg_id is not None and label:
            heatmaps.setdefault(ecg_id, {})[label] = str(path)
    return {"raw": raw, "cwt": cwt, "stft": stft, "heatmaps": heatmaps}


@st.cache_data
def build_case_catalog(report_dir: str, manifest_path: str) -> list[dict]:
    assets = build_asset_maps(report_dir)
    metadata = load_case_metadata(manifest_path)
    cases = []
    for ecg_id, cwt_path in assets["cwt"].items():
        case = {"ecg_id": ecg_id, "cwt_path": cwt_path, "raw_path": assets["raw"].get(ecg_id), "stft_path": assets["stft"].get(ecg_id)}
        case.update(metadata.get(ecg_id, {}))
        case["heatmaps"] = assets["heatmaps"].get(ecg_id, {})
        cases.append(case)
    return sorted(cases, key=lambda case: (case.get("split") != "test", case["ecg_id"]))


@st.cache_data
def build_representative_catalog(report_dir: str, manifest_path: str) -> list[dict]:
    assets = build_asset_maps(report_dir)
    metadata = load_case_metadata(manifest_path)
    samples = cached_csv(str(Path(report_dir) / "representative_samples.csv"))
    ids = set(samples["ecg_id"].astype(int).tolist()) if samples is not None and "ecg_id" in samples else set()
    ids.update(assets["cwt"].keys())
    cases = []
    for ecg_id in sorted(ids):
        case = {
            "ecg_id": ecg_id,
            "raw_path": assets["raw"].get(ecg_id),
            "cwt_path": assets["cwt"].get(ecg_id),
            "stft_path": assets["stft"].get(ecg_id),
            "heatmaps": assets["heatmaps"].get(ecg_id, {}),
        }
        case.update(metadata.get(ecg_id, {}))
        cases.append(case)
    return cases


def case_display_name(case: dict) -> str:
    patient = f"P-{case['patient_id']}" if case.get("patient_id") is not None else "Patient ID unavailable"
    split = str(case.get("split", "reference")).title()
    return f"{patient} | ECG {case['ecg_id']:05d} | {split} record"


def case_heading(case: dict | None) -> str:
    if not case:
        return "External CWT image"
    patient = f"PTB-XL Patient Case P-{case['patient_id']}" if case.get("patient_id") is not None else "PTB-XL Patient Case"
    return patient


def clear_review_state(input_key: str) -> None:
    if st.session_state.get("review_input_key") == input_key:
        return
    for key in [
        "review_prediction",
        "review_result_source",
        "review_labels",
        "review_cam",
        "review_cam_target",
        "review_cam_key",
        "last_gradcam_path",
    ]:
        st.session_state.pop(key, None)
    st.session_state["review_input_key"] = input_key


def run_image_prediction(image: Image.Image) -> tuple[pd.DataFrame, list[str], str]:
    model, labels, checkpoint, device = load_runtime_model()
    if model is None:
        raise RuntimeError("No compatible model checkpoint is available.")
    transform = eval_transform(IMAGE_SIZE)
    probabilities = predict_image(model, image, transform, labels, device)
    thresholds = load_thresholds(ARTIFACT_ROOT, labels, checkpoint)
    return prediction_table(probabilities, thresholds), labels, device


def load_stored_test_result(ecg_id: int) -> pd.DataFrame | None:
    predictions = cached_csv(str(REPORT_DIR / "test_predictions.csv"))
    if predictions is None or "ecg_id" not in predictions:
        return None
    row = predictions.loc[predictions["ecg_id"].astype(int) == int(ecg_id)]
    if row.empty:
        return None
    row = row.iloc[0]
    columns = [f"prob_{label}" for label in LABELS]
    if not all(column in row.index for column in columns):
        return None
    probabilities = pd.DataFrame({"label": LABELS, "probability": [float(row[f"prob_{label}"]) for label in LABELS]})
    return prediction_table(probabilities, load_thresholds(ARTIFACT_ROOT, LABELS))


@st.cache_data
def load_quality_by_label(path: str) -> dict[str, dict[str, float]]:
    frame = read_csv_if_exists(Path(path))
    if frame is None:
        return {}
    return {
        str(row.label): {"f1": float(row.f1), "auroc": float(row.auroc), "auprc": float(row.auprc)}
        for row in frame.itertuples(index=False)
    }


def render_case_header(case: dict | None, cwt_image: Image.Image, source_name: str) -> None:
    with st.container(border=True):
        overview, record, age, input_status = st.columns([1.7, 1, 0.7, 1])
        with overview:
            st.markdown(f"### {case_heading(case)}")
            st.caption("De-identified PTB-XL research case. This is not an active clinical patient chart.")
        with record:
            record_id = f"ECG {case['ecg_id']:05d}" if case else "External image"
            st.metric("Recording", record_id)
        with age:
            age_value = f"{case['age']} y" if case and case.get("age") is not None else "Not supplied"
            st.metric("Age", age_value)
        with input_status:
            st.metric("CWT input", "Available")
        st.caption(f"Input source: {source_name} | Image dimensions: {cwt_image.width} x {cwt_image.height} | Model tensor: {IMAGE_SIZE} x {IMAGE_SIZE}")


def render_signal_review(case: dict | None, cwt_image: Image.Image, input_name: str) -> None:
    section_title("Signal review", "Inspect the original 12-lead waveform separately from the exact CWT image supplied to the model.")
    raw_tab, cwt_tab, stft_tab = st.tabs(["Raw 12-lead ECG", "CWT model input", "STFT research view"])
    with raw_tab:
        raw_path = Path(case["raw_path"]) if case and case.get("raw_path") else None
        if raw_path and raw_path.exists():
            st.image(str(raw_path), caption="Raw 12-lead waveform. This is the signal clinicians should inspect.", width="stretch")
        else:
            st.info("No raw waveform artifact is available for this input.")
    with cwt_tab:
        st.image(cwt_image, caption=f"CWT 12-lead grid used for model inference: {input_name}", width="stretch")
        st.caption("Representation contract: Morlet CWT, 12 leads, 100 Hz source signal, resized only at inference.")
    with stft_tab:
        stft_path = Path(case["stft_path"]) if case and case.get("stft_path") else None
        if stft_path and stft_path.exists():
            st.image(str(stft_path), caption="STFT visualization retained for research inspection only. It is not input to the current checkpoint.", width="stretch")
        else:
            st.info("No STFT visual is packaged for this patient case.")


def split_saved_explanation(path: Path) -> tuple[Image.Image, Image.Image] | None:
    image = Image.open(path).convert("RGB")
    if image.width < 3:
        return None
    panel_width = image.width // 3
    return image.crop((0, 0, panel_width, image.height)), image.crop((panel_width * 2, 0, image.width, image.height))


def render_explanation(case: dict | None, cwt_image: Image.Image, ranked: pd.DataFrame) -> None:
    section_title("Model attention", "Optional research explanation for one ranked output. It is not a localization or a clinical finding.")
    targets = ranked["label"].astype(str).tolist()
    target = st.selectbox("Output to explain", targets, format_func=lambda label: f"{label} - {LABEL_DETAILS.get(label, (label, ''))[0]}")
    target_row = ranked.loc[ranked["label"] == target].iloc[0]
    st.caption(
        f"Selected output: {target} | model score {float(target_row.probability) * 100:.1f}% | "
        f"{target_row.review_state}."
    )

    saved_path = None
    if case:
        value = case.get("heatmaps", {}).get(target)
        saved_path = Path(value) if value else None
    generated = st.session_state.get("review_cam")
    generated_matches = (
        generated is not None
        and st.session_state.get("review_cam_target") == target
        and st.session_state.get("review_cam_key") == st.session_state.get("review_input_key")
    )

    if generated_matches:
        left, right = st.columns(2, gap="medium")
        left.image(cwt_image, caption="CWT model input", width="stretch")
        right.image(generated["overlay"], caption=f"Grad-CAM overlay for {target}", width="stretch")
        if st.button("Save Grad-CAM overlay"):
            output_path = REPORT_DIR / f"ui_gradcam_{timestamp()}_{target}.png"
            save_overlay(output_path, generated["overlay"])
            st.session_state["last_gradcam_path"] = output_path
            st.success(f"Saved: {output_path.name}")
    elif saved_path and saved_path.exists():
        panels = split_saved_explanation(saved_path)
        if panels:
            left, right = st.columns(2, gap="medium")
            left.image(panels[0], caption="Stored CWT input", width="stretch")
            right.image(panels[1], caption=f"Stored Grad-CAM overlay for {target}", width="stretch")
        else:
            st.image(str(saved_path), caption=f"Stored Grad-CAM explanation for {target}", width="stretch")
        st.caption("Stored research artifact. Recompute only when investigating a specific output.")
    else:
        st.info("No stored explanation is paired with this output. You can compute one from the loaded checkpoint.")

    if st.button("Recompute Grad-CAM overlay", help="This loads the vision model if needed and may take longer on CPU."):
        model, labels, _, device = load_runtime_model()
        transform = eval_transform(IMAGE_SIZE)
        with st.spinner(f"Computing Grad-CAM for {target}..."):
            _, _, overlay = generate_gradcam(model, transform(cwt_image).unsqueeze(0), cwt_image, labels.index(target), device)
        st.session_state["review_cam"] = {"overlay": overlay}
        st.session_state["review_cam_target"] = target
        st.session_state["review_cam_key"] = st.session_state.get("review_input_key")
        st.rerun()
    st.warning(
        "Grad-CAM is a low-resolution (approximately 7 x 7) model-attention map interpolated over the CWT grid. "
        "Warmer color means higher relative model attention, not signal amplitude, anatomy, causality, or lesion location."
    )


def render_export(table: pd.DataFrame, input_name: str) -> None:
    content = build_markdown_report("VinStroke ECG Research Review", table, input_name, st.session_state.get("last_gradcam_path"))
    left, right = st.columns(2)
    with left:
        st.download_button("Download research review", data=content, file_name=f"VinStroke_ECG_review_{timestamp()}.md", mime="text/markdown", type="primary", width="stretch")
    with right:
        if st.button("Save review to research artifacts", width="stretch"):
            path = REPORT_DIR / f"ui_review_{timestamp()}.md"
            save_markdown_report(path, "VinStroke ECG Research Review", table, input_name, st.session_state.get("last_gradcam_path"))
            st.success(f"Saved: {path.name}")


def clinical_review_page() -> None:
    page_header("Patient Case Review", "Review five ECG superclass outputs for one de-identified patient case, then inspect the source waveform and optional model attention.")
    research_notice()
    source = st.radio("Case source", ["PTB-XL patient case", "Upload CWT image"], horizontal=True)
    case = None
    input_name = ""

    if source == "PTB-XL patient case":
        cases = build_case_catalog(str(REPORT_DIR), str(MANIFEST_DIR / "manifest_images_full.csv"))
        if not cases:
            st.error("No inference-ready CWT patient cases are packaged in the artifacts.")
            return
        index = st.selectbox("De-identified patient case", range(len(cases)), format_func=lambda item: case_display_name(cases[item]))
        case = cases[index]
        cwt_path = Path(case["cwt_path"])
        cwt_image = Image.open(cwt_path).convert("RGB")
        input_name = cwt_path.name
        input_key = f"case:{cwt_path.resolve()}"
        source_name = "Packaged PTB-XL CWT representation"
    else:
        uploaded = st.file_uploader("CWT 12-lead grid", type=["png", "jpg", "jpeg"])
        if uploaded is None:
            st.info("Upload a CWT 12-lead grid generated with the same preprocessing contract to start a review.")
            return
        image_bytes = uploaded.getvalue()
        cwt_image = load_uploaded_image(uploaded)
        input_name = uploaded.name
        input_key = f"upload:{hashlib.sha256(image_bytes).hexdigest()}"
        source_name = "Uploaded CWT representation"

    clear_review_state(input_key)
    render_case_header(case, cwt_image, source_name)
    stored = load_stored_test_result(case["ecg_id"]) if case else None
    if st.session_state.get("review_prediction") is None and stored is not None:
        st.session_state["review_prediction"] = stored
        st.session_state["review_labels"] = LABELS
        st.session_state["review_result_source"] = "Stored held-out PTB-XL test inference"

    summary_tab, signal_tab, explanation_tab, export_tab = st.tabs(
        ["1. AI triage", "2. Signal review", "3. Model attention", "4. Export"]
    )
    with summary_tab:
        section_title("Five-label triage", "Every patient case is ranked in one fixed order: abnormal screen-positive, near threshold, normal-pattern support, then below threshold.")
        table = st.session_state.get("review_prediction")
        if table is None:
            st.info("No stored result is available for this case. Run the current checkpoint to generate all five outputs.")
        else:
            source_text = st.session_state.get("review_result_source", "Current checkpoint inference")
            st.caption(f"Result source: {source_text}")
            ranked = rank_prediction_results(table, load_quality_by_label(str(REPORT_DIR / "per_class_metrics.csv")))
            render_ranked_predictions(ranked)
            with st.expander("Why performance differs by label"):
                st.caption("Held-out test evidence is shown for each label. In this run, HYP has materially lower F1 and AUPRC than NORM, MI, STTC, and CD, so it is explicitly marked as limited evidence.")
                label_reference()

        if not model_available():
            st.error("The model checkpoint is missing; dynamic inference is unavailable.")
        elif st.button("Run current checkpoint", type="primary", help="Required for uploads and optional for re-running a packaged case. The first CPU run loads a 1 GB ConvNeXtV2 checkpoint."):
            with st.spinner("Running the CWT model for all five labels..."):
                table, labels, _ = run_image_prediction(cwt_image)
            st.session_state["review_prediction"] = table
            st.session_state["review_labels"] = labels
            st.session_state["review_result_source"] = "Current checkpoint inference"
            st.rerun()
    with signal_tab:
        render_signal_review(case, cwt_image, input_name)
    with explanation_tab:
        table = st.session_state.get("review_prediction")
        if table is None:
            st.info("Generate the five-label result first, then select one output for model-attention review.")
        else:
            ranked = rank_prediction_results(table, load_quality_by_label(str(REPORT_DIR / "per_class_metrics.csv")))
            render_explanation(case, cwt_image, ranked)
    with export_tab:
        table = st.session_state.get("review_prediction")
        if table is None:
            st.info("Generate the five-label result before exporting a research review.")
        else:
            render_export(table, input_name)


def metric_value(frame: pd.DataFrame | None, key: str) -> float | None:
    if frame is None or frame.empty or key not in frame.columns:
        return None
    return float(frame.iloc[0][key])


def show_plot(path: Path, caption: str) -> None:
    if path.exists():
        st.image(str(path), caption=caption, width="stretch")
    else:
        st.info(f"Artifact unavailable: {path.name}")


def research_evidence_page() -> None:
    page_header("Research Evidence", "Trace every visual to its real representation and separate patient-case inputs from validation, calibration, and training artifacts.", "Experiment evidence")
    research_notice()
    cases, dataset, validation, training = st.tabs(["Case representations", "Dataset", "Validation", "Training"])
    with cases:
        section_title("Representative case assets", "Raw waveform, CWT and STFT are shown with their actual roles. A raw waveform alone is not valid input to the CWT checkpoint.")
        catalog = build_representative_catalog(str(REPORT_DIR), str(MANIFEST_DIR / "manifest_images_full.csv"))
        if not catalog:
            st.info("No representative assets are available.")
        else:
            index = st.selectbox("Research patient case", range(len(catalog)), format_func=lambda item: case_display_name(catalog[item]))
            case = catalog[index]
            rows = []
            for representation, key, role in [
                ("Raw 12-lead ECG", "raw_path", "Clinician waveform review"),
                ("CWT grid", "cwt_path", "Required model input"),
                ("STFT grid", "stft_path", "Research visualization only"),
            ]:
                rows.append({"Representation": representation, "Availability": "Available" if case.get(key) else "Not packaged", "Role": role})
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            if not case.get("cwt_path"):
                st.warning("This reference case does not include a CWT image. Do not send its raw waveform image to the current vision checkpoint.")
            raw_tab, cwt_tab, stft_tab = st.tabs(["Raw ECG", "CWT", "STFT"])
            for tab, key, caption in [
                (raw_tab, "raw_path", "Raw 12-lead waveform"),
                (cwt_tab, "cwt_path", "CWT 12-lead model input"),
                (stft_tab, "stft_path", "STFT research visualization")
            ]:
                with tab:
                    value = case.get(key)
                    if value and Path(value).exists():
                        st.image(value, caption=caption, width="stretch")
                    else:
                        st.info("Not packaged for this research case.")
    with dataset:
        section_title("Dataset and labels", "PTB-XL contains 21,430 target records from 18,637 de-identified patients in this prepared manifest.")
        c1, c2 = st.columns(2)
        with c1:
            show_plot(REPORT_DIR / "class_counts.png", "Diagnostic superclass counts")
        with c2:
            show_plot(REPORT_DIR / "label_cooccurrence_matrix.png", "Multi-label co-occurrence")
        c3, c4 = st.columns(2)
        with c3:
            show_plot(REPORT_DIR / "multi_label_cardinality.png", "Diagnostic labels per ECG")
        with c4:
            show_plot(REPORT_DIR / "split_distribution.png", "Patient-aware split distribution")
    with validation:
        section_title("Held-out model validation", "Performance is reported per diagnostic superclass so the UI does not imply uniform reliability.")
        per_class = cached_csv(str(REPORT_DIR / "per_class_metrics.csv"))
        if per_class is not None:
            st.dataframe(per_class, width="stretch", hide_index=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            show_plot(REPORT_DIR / "per_class_auroc.png", "Per-class AUROC")
        with c2:
            show_plot(REPORT_DIR / "per_class_auprc.png", "Per-class AUPRC")
        with c3:
            show_plot(REPORT_DIR / "per_class_f1.png", "Per-class F1")
        c4, c5 = st.columns(2)
        with c4:
            show_plot(REPORT_DIR / "calibration_curve_macro.png", "Macro calibration")
        with c5:
            show_plot(REPORT_DIR / "prediction_example_ground_truth_vs_probability.png", "Test prediction example")
    with training:
        section_title("Training and ablation", "The current artifact contains the CWT main model result; the ablation record does not yet compare additional trained representations.")
        c1, c2 = st.columns(2)
        with c1:
            show_plot(REPORT_DIR / "training_loss_curve.png", "Training loss")
        with c2:
            show_plot(REPORT_DIR / "validation_metrics_curve.png", "Validation metrics")
        show_plot(REPORT_DIR / "ablation_results_bar_chart.png", "Current ablation record")


def about_page() -> None:
    page_header("System and Safety", "The current scope is multi-label ECG superclass screening from a CWT grid, not stroke prediction or clinical diagnosis.", "Technical reference")
    research_notice()
    left, right = st.columns(2)
    with left:
        st.markdown("### Model contract")
        st.markdown(
            f"""
            - **Dataset:** PTB-XL; 21,430 target ECG records and 18,637 de-identified patients.
            - **Input:** 12-lead Morlet CWT grid from a 100 Hz, 10-second ECG.
            - **Backbone:** {CONFIG.get('model_name', 'ConvNeXtV2')}.
            - **Outputs:** independent sigmoid scores for {', '.join(LABELS)}.
            - **Thresholds:** optimized on the validation split for each label.
            """
        )
    with right:
        st.markdown("### Interpretation boundary")
        st.markdown(
            "This system does not predict stroke outcome. It screens five PTB-XL diagnostic superclasses. "
            "AFIB appears in the dataset analysis, but it is not a trained output head in the packaged checkpoint. "
            "Raw waveform images, CWT grids, STFT visuals and Grad-CAM overlays have distinct roles and must not be substituted for one another."
        )
    section_title("Five output labels", "An independent score above threshold is a screen-positive model output, not a diagnosis.")
    label_reference()
    section_title("Use safeguards", "A qualified clinician must retain responsibility for ECG interpretation and any patient-care decision.")
    st.markdown(
        """
        - Confirm the source waveform, acquisition quality, lead placement and patient context outside this prototype.
        - Treat the score as model output, not disease probability, severity, prognosis or stroke risk.
        - Use per-label held-out evidence to understand performance limits; HYP is the weakest class in this run.
        - Treat model attention as a research aid, not evidence of anatomical localization or causality.
        - Do not use this prototype as a production clinical device without external validation, workflow testing and governance review.
        """
    )


def main() -> None:
    with st.sidebar:
        sidebar_brand()
        page = st.radio("Workspace", ["Patient case review", "Research evidence", "System and safety"])
        st.markdown("---")
        if model_available():
            st.success("Checkpoint available")
            st.caption(f"{CHECKPOINT_PATH.name} | {CHECKPOINT_PATH.stat().st_size / (1024**3):.2f} GB")
        else:
            st.error("Checkpoint missing")
        st.caption("VinStroke ECG is an independent research prototype. The visual theme does not imply Vinmec deployment approval or clinical validation.")

    if page == "Patient case review":
        clinical_review_page()
    elif page == "Research evidence":
        research_evidence_page()
    else:
        about_page()


if __name__ == "__main__":
    main()
