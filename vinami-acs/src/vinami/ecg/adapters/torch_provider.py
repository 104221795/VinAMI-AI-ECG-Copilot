"""Optional ConvNeXtV2 research adapter kept below the ECG AI provider port."""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from math import isfinite, sqrt
from pathlib import Path
from time import perf_counter
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from vinami.ecg.domain.clinical import STANDARD_12_LEADS
from vinami.ecg.ports.provider import (
    AIProviderHealth,
    ECGExplanationRequest,
    ECGExplanationResult,
    ECGPredictionRequest,
    ECGPredictionResult,
    InputValidationResult,
    ModelInfo,
)

EXPECTED_LABEL_ORDER = ("NORM", "MI", "STTC", "CD", "HYP")
SAFE_DISPLAY_LABELS = {
    "NORM": "NORM",
    "MI": "MI-related ECG pattern",
    "STTC": "ST/T change",
    "CD": "conduction disturbance",
    "HYP": "hypertrophy pattern",
}
EXPECTED_SAMPLING_RATE_HZ = 100.0
EXPECTED_SAMPLES_PER_LEAD = 1000
EXPECTED_IMAGE_SIZE = 224
PREPROCESSING_VERSION = "ptbxl-cwt-grid-adapter-r23a-v2"
LABEL_MAPPING_VERSION = "ptbxl-5-safe-labels-r23a-v1"
INPUT_CONTRACT = (
    "VinAMI canonical 12-lead waveform JSON, 100 Hz, 10 seconds, 1000 samples per "
    "lead, lead order I/II/III/aVR/aVL/aVF/V1-V6; adapter renders a 224x224 RGB "
    "CWT grid for the ConvNeXtV2 PTB-XL research checkpoint."
)


@dataclass(frozen=True, slots=True)
class _WaveformInput:
    samples: NDArray[np.float32]
    parser_warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _PreparedImage:
    image_bytes: bytes
    preprocessing_version: str
    warnings: tuple[str, ...]


class TorchConvNeXtV2Provider:
    """Run the verified PTB-XL ConvNeXtV2 checkpoint behind the provider port.

    The adapter is intentionally optional. Importing business, workflow, or API modules never
    imports torch-specific code directly; this class is only composed when runtime configuration
    supplies a checkpoint path and expected checksum.
    """

    def __init__(
        self,
        checkpoint: Path,
        expected_checksum: str,
        device: str = "cpu",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._checkpoint = checkpoint
        self._expected_checksum = expected_checksum.lower()
        self._device_name = device
        self._timeout_seconds = timeout_seconds
        self._model: Any = None
        self._metadata: dict[str, Any] | None = None

    def get_model_info(self) -> ModelInfo:
        metadata = self._load_metadata()
        return ModelInfo(
            name=str(metadata["config"]["model_name"]),
            version=f"checkpoint-epoch-{metadata['epoch']}",
            provider_name="torch-convnextv2-ptbxl-research",
            input_contract=INPUT_CONTRACT,
            synthetic=False,
            checkpoint_checksum=self._expected_checksum,
            label_order=EXPECTED_LABEL_ORDER,
            threshold_source="checkpoint validation metadata",
        )

    def health(self) -> AIProviderHealth:
        try:
            self._verify_file()
            import timm  # noqa: F401
            import torch  # noqa: F401
            import torchvision  # noqa: F401

            self._validate_metadata(self._load_metadata())
        except Exception as error:
            return AIProviderHealth(
                False,
                "torch-convnextv2-ptbxl-research",
                f"unavailable: {type(error).__name__}: {_safe_text(str(error))}",
            )
        return AIProviderHealth(
            True,
            "torch-convnextv2-ptbxl-research",
            (
                "real research checkpoint available; provider is for research-use model scores "
                "and does not create clinical authority"
            ),
        )

    def validate_input(self, request: ECGPredictionRequest) -> InputValidationResult:
        if request.input_quality in {"poor", "insufficient", "unsupported", "failed"}:
            return InputValidationResult(
                False,
                ("Technical ECG quality blocks normal model-score presentation.",),
                "technical ECG quality blocks analysis",
            )
        if request.image_bytes is not None:
            return self._validate_image_input(request.image_bytes)
        if request.waveform_bytes is None:
            return InputValidationResult(
                False,
                failure_reason=(
                    "canonical 12-lead waveform bytes or verified CWT image bytes are required"
                ),
            )
        try:
            waveform = _parse_waveform(request.waveform_bytes)
        except ValueError as error:
            return InputValidationResult(False, failure_reason=str(error))
        return InputValidationResult(True, waveform.parser_warnings)

    def predict(self, request: ECGPredictionRequest) -> ECGPredictionResult:
        validation = self.validate_input(request)
        if not validation.valid:
            raise ValueError(validation.failure_reason)
        model, metadata, torch = self._load_model()
        from PIL import Image
        from torchvision import transforms

        started_at = datetime.now(UTC)
        started = perf_counter()
        prepared = self._prepare_image(request)
        image = Image.open(BytesIO(prepared.image_bytes)).convert("RGB")
        tensor = (
            transforms.Compose(
                [
                    transforms.Resize((EXPECTED_IMAGE_SIZE, EXPECTED_IMAGE_SIZE)),
                    transforms.ToTensor(),
                    transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
                ]
            )(image)
            .unsqueeze(0)
            .to(self._device_name)
        )
        with torch.inference_mode():
            values = torch.sigmoid(model(tensor))[0].detach().cpu().tolist()
        duration_ms = round((perf_counter() - started) * 1000)
        if duration_ms > self._timeout_seconds * 1000:
            raise TimeoutError("ECG AI provider exceeded configured inference timeout")
        labels = EXPECTED_LABEL_ORDER
        thresholds = {str(key): float(value) for key, value in metadata["threshold"].items()}
        scores = dict(zip(labels, (round(float(value), 6) for value in values), strict=True))
        completed_at = datetime.now(UTC)
        warnings = (
            "Research-use ECG model score; not a diagnosis or clinical probability.",
            f"Inference duration {duration_ms} ms.",
            *prepared.warnings,
            *validation.warnings,
        )
        return ECGPredictionResult(
            request.study_id,
            str(metadata["config"]["model_name"]),
            f"checkpoint-epoch-{metadata['epoch']}",
            "torch-convnextv2-ptbxl-research",
            started_at,
            completed_at,
            request.input_quality,
            scores,
            thresholds,
            tuple(
                SAFE_DISPLAY_LABELS[label] for label in labels if scores[label] >= thresholds[label]
            ),
            (),
            _dedupe(warnings),
            {
                "checkpoint_sha256": self._expected_checksum,
                "device": self._device_name,
                "input_artifact_checksum": request.artifact_checksum or "unavailable",
                "input_contract": INPUT_CONTRACT,
                "label_mapping_version": LABEL_MAPPING_VERSION,
                "preprocessing_version": prepared.preprocessing_version,
                "execution_time_ms": str(duration_ms),
                "provider_kind": "real-research-checkpoint",
            },
            None,
            False,
        )

    def explain(self, request: ECGExplanationRequest) -> ECGExplanationResult:
        if request.target_label not in EXPECTED_LABEL_ORDER:
            return ECGExplanationResult(
                request.study_id,
                request.target_label,
                "unavailable",
                "Grad-CAM target label is outside the fixed R23A label mapping.",
                synthetic=False,
            )
        try:
            model, _metadata, torch = self._load_model()
            from PIL import Image
            from torchvision import transforms

            prepared = self._prepare_image(
                ECGPredictionRequest(
                    request.study_id,
                    request.input_reference,
                    image_bytes=request.image_bytes,
                    waveform_bytes=request.waveform_bytes,
                    input_quality=request.input_quality,
                    artifact_checksum=request.artifact_checksum,
                )
            )
            image = Image.open(BytesIO(prepared.image_bytes)).convert("RGB")
            tensor = (
                transforms.Compose(
                    [
                        transforms.Resize((EXPECTED_IMAGE_SIZE, EXPECTED_IMAGE_SIZE)),
                        transforms.ToTensor(),
                        transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
                    ]
                )(image)
                .unsqueeze(0)
                .to(self._device_name)
            )
            target_layer = _last_conv_layer(model, torch)
            activations: list[Any] = []
            gradients: list[Any] = []

            def _capture_activation(_module: Any, _inputs: Any, output: Any) -> None:
                activations.append(output.detach())

            def _capture_gradient(_module: Any, _grad_inputs: Any, grad_outputs: Any) -> None:
                gradients.append(grad_outputs[0].detach())

            forward_handle = target_layer.register_forward_hook(_capture_activation)
            backward_handle = target_layer.register_full_backward_hook(_capture_gradient)
            try:
                model.zero_grad(set_to_none=True)
                logits = model(tensor)
                target = logits[0, EXPECTED_LABEL_ORDER.index(request.target_label)]
                target.backward()
            finally:
                forward_handle.remove()
                backward_handle.remove()
            if not activations or not gradients:
                raise RuntimeError("Grad-CAM hooks did not capture model tensors")
            heatmap = _gradcam_array(activations[-1], gradients[-1], torch)
            content = _gradcam_overlay_png(image, heatmap, request.target_label)
            return ECGExplanationResult(
                request.study_id,
                request.target_label,
                f"gradcam://{request.study_id}/{request.target_label}",
                (
                    "Grad-CAM is a model-attention aid for physician review; it is not causal "
                    "clinical evidence or lesion localization."
                ),
                content,
                "image/png",
                synthetic=False,
            )
        except Exception as error:
            return ECGExplanationResult(
                request.study_id,
                request.target_label,
                "unavailable",
                f"Grad-CAM artifact unavailable: {type(error).__name__}: {_safe_text(str(error))}",
                synthetic=False,
            )

    def _validate_image_input(self, content: bytes) -> InputValidationResult:
        try:
            from PIL import Image

            with Image.open(BytesIO(content)) as image:
                warnings: tuple[str, ...] = ()
                if image.size != (EXPECTED_IMAGE_SIZE, EXPECTED_IMAGE_SIZE):
                    warnings = ("Provided ECG image will be resized to the model input size.",)
                image.verify()
        except Exception as error:
            return InputValidationResult(
                False,
                failure_reason=f"ECG image input is malformed: {type(error).__name__}",
            )
        return InputValidationResult(True, warnings)

    def _prepare_image(self, request: ECGPredictionRequest) -> _PreparedImage:
        if request.image_bytes is not None:
            return _PreparedImage(
                request.image_bytes,
                "provided-cwt-image-r23a-v1",
                ("Pre-rendered ECG image input used; waveform lead validation is limited.",),
            )
        if request.waveform_bytes is None:
            raise ValueError("canonical waveform bytes are required")
        waveform = _parse_waveform(request.waveform_bytes)
        image_bytes, cwt_warnings = _render_cwt_grid(waveform.samples)
        return _PreparedImage(
            image_bytes,
            PREPROCESSING_VERSION,
            (
                "Canonical waveform was transformed to a CWT grid inside the provider adapter.",
                *waveform.parser_warnings,
                *cwt_warnings,
            ),
        )

    def _verify_file(self) -> None:
        if not self._checkpoint.is_file():
            raise FileNotFoundError("research checkpoint is unavailable")
        digest_builder = sha256()
        with self._checkpoint.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest_builder.update(chunk)
        digest = digest_builder.hexdigest()
        if digest != self._expected_checksum:
            raise ValueError("research checkpoint checksum mismatch")

    def _load_metadata(self) -> dict[str, Any]:
        if self._metadata is None:
            self._verify_file()
            import torch

            value = torch.load(self._checkpoint, map_location="cpu", weights_only=False)
            required = {"model_state_dict", "config", "label_names", "threshold", "epoch"}
            if not isinstance(value, dict) or not required.issubset(value):
                raise ValueError("research checkpoint contract is incompatible")
            self._validate_metadata(value)
            self._metadata = value
        return self._metadata

    def _load_model(self) -> tuple[Any, dict[str, Any], Any]:
        metadata = self._load_metadata()
        import timm
        import torch

        if self._model is None:
            model = timm.create_model(
                str(metadata["config"]["model_name"]),
                pretrained=False,
                num_classes=len(EXPECTED_LABEL_ORDER),
            )
            model.load_state_dict(metadata["model_state_dict"], strict=True)
            model.to(self._device_name).eval()
            self._model = model
        return self._model, metadata, torch

    def _validate_metadata(self, metadata: dict[str, Any]) -> None:
        labels = tuple(str(item) for item in metadata.get("label_names", ()))
        if labels != EXPECTED_LABEL_ORDER:
            raise ValueError("research checkpoint label order is incompatible with R23A")
        config = metadata.get("config")
        if not isinstance(config, dict):
            raise ValueError("research checkpoint configuration is missing")
        if str(config.get("model_name")) != "convnextv2_base":
            raise ValueError("research checkpoint model architecture is incompatible")
        if int(config.get("sampling_rate", 0)) != int(EXPECTED_SAMPLING_RATE_HZ):
            raise ValueError("research checkpoint sampling-rate contract is incompatible")
        if int(config.get("signal_length", 0)) != EXPECTED_SAMPLES_PER_LEAD:
            raise ValueError("research checkpoint signal-length contract is incompatible")
        thresholds = metadata.get("threshold")
        if not isinstance(thresholds, dict) or not set(EXPECTED_LABEL_ORDER).issubset(thresholds):
            raise ValueError("research checkpoint thresholds are incomplete")


def _parse_waveform(content: bytes) -> _WaveformInput:
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("canonical waveform JSON is malformed") from error
    if not isinstance(value, dict):
        raise ValueError("canonical waveform JSON must be an object")
    sampling_rate = _float_field(value, "sampling_rate_hz")
    if abs(sampling_rate - EXPECTED_SAMPLING_RATE_HZ) > 1e-6:
        raise ValueError("PTB-XL checkpoint expects 100 Hz ECG waveform input")
    unit = str(value.get("amplitude_unit", "")).strip()
    if unit != "uV":
        raise ValueError("normalized ECG waveform must use uV amplitude units")
    raw_leads = value.get("leads")
    if not isinstance(raw_leads, list):
        raise ValueError("canonical waveform leads are missing")
    lead_names = tuple(_lead_name(item) for item in raw_leads)
    if lead_names != STANDARD_12_LEADS:
        raise ValueError("ECG waveform must contain the standard 12 leads in canonical order")
    rows: list[list[float]] = []
    for lead in raw_leads:
        samples = _lead_samples(lead)
        if len(samples) != EXPECTED_SAMPLES_PER_LEAD:
            raise ValueError("PTB-XL checkpoint expects 1000 samples per lead")
        rows.append(samples)
    samples_array = np.asarray(rows, dtype=np.float32)
    if not np.all(np.isfinite(samples_array)):
        raise ValueError("ECG waveform contains non-finite sample values")
    flat_leads = [
        lead
        for lead, row in zip(STANDARD_12_LEADS, samples_array, strict=True)
        if float(np.ptp(row)) < 1e-6
    ]
    if flat_leads:
        raise ValueError(
            f"ECG waveform contains flat or missing lead data: {', '.join(flat_leads)}"
        )
    max_abs = float(np.max(np.abs(samples_array)))
    if max_abs > 100_000:
        raise ValueError("ECG waveform amplitude range is outside the supported technical contract")
    parser_warnings = tuple(str(item) for item in value.get("parser_warnings", []) if str(item))
    return _WaveformInput(samples_array, parser_warnings)


def _float_field(value: dict[str, Any], key: str) -> float:
    try:
        parsed = float(value[key])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"canonical waveform field is missing or invalid: {key}") from error
    if not isfinite(parsed):
        raise ValueError(f"canonical waveform field is non-finite: {key}")
    return parsed


def _lead_name(value: Any) -> str:
    if not isinstance(value, dict):
        raise ValueError("canonical waveform lead entry is malformed")
    name = str(value.get("name", "")).strip()
    if not name:
        raise ValueError("canonical waveform lead name is missing")
    return name


def _lead_samples(value: Any) -> list[float]:
    if not isinstance(value, dict) or not isinstance(value.get("samples"), list):
        raise ValueError("canonical waveform lead samples are missing")
    parsed: list[float] = []
    for sample in value["samples"]:
        try:
            numeric = float(sample)
        except (TypeError, ValueError) as error:
            raise ValueError("canonical waveform sample is not numeric") from error
        if not isfinite(numeric):
            raise ValueError("canonical waveform sample is non-finite")
        parsed.append(numeric)
    return parsed


def _render_cwt_grid(samples: NDArray[np.float32]) -> tuple[bytes, tuple[str, ...]]:
    from PIL import Image

    warnings: list[str] = []
    rows = 4
    columns = 3
    tile_width = EXPECTED_IMAGE_SIZE // columns
    tile_height = EXPECTED_IMAGE_SIZE // rows
    canvas = Image.new("L", (tile_width * columns, tile_height * rows), 0)
    for index, _lead in enumerate(STANDARD_12_LEADS):
        row = index // columns
        column = index % columns
        cwt, cwt_warnings = _cwt_image(_normalize_signal(samples[index]))
        warnings.extend(cwt_warnings)
        tile = Image.fromarray(
            (_normalize_image(cwt) * 255).astype(np.uint8),
            mode="L",
        )
        tile = tile.resize((tile_width, tile_height), Image.Resampling.BICUBIC)
        canvas.paste(tile, (column * tile_width, row * tile_height))
    if canvas.size != (EXPECTED_IMAGE_SIZE, EXPECTED_IMAGE_SIZE):
        canvas = canvas.resize((EXPECTED_IMAGE_SIZE, EXPECTED_IMAGE_SIZE), Image.Resampling.BICUBIC)
    output = BytesIO()
    canvas.convert("RGB").save(output, format="PNG")
    return output.getvalue(), _dedupe(tuple(warnings))


def _normalize_signal(signal: NDArray[np.float32]) -> NDArray[np.float32]:
    centered = signal.astype(np.float32) - np.nanmean(signal)
    std = float(np.nanstd(centered))
    if std > 0:
        centered = centered / std
    return centered.astype(np.float32)


def _cwt_image(signal: NDArray[np.float32]) -> tuple[NDArray[np.float32], tuple[str, ...]]:
    try:
        pywt: Any = importlib.import_module("pywt")
        scales = np.arange(1, 33, dtype=np.float32)
        coeffs, _ = pywt.cwt(
            signal,
            scales,
            "morl",
            sampling_period=1.0 / EXPECTED_SAMPLING_RATE_HZ,
        )
        image = np.log1p(np.abs(np.asarray(coeffs, dtype=np.float32)))
        return image.astype(np.float32), ()
    except ModuleNotFoundError:
        return (
            _fallback_morlet_cwt(signal),
            ("PyWavelets is unavailable; deterministic Morlet-convolution fallback was used.",),
        )


def _fallback_morlet_cwt(signal: NDArray[np.float32]) -> NDArray[np.float32]:
    coefficients: list[NDArray[np.float32]] = []
    for scale in range(1, 33):
        width = max(9, int(scale * 8))
        if width % 2 == 0:
            width += 1
        axis = np.linspace(-4.0, 4.0, width, dtype=np.float32)
        wavelet = np.cos(5.0 * axis) * np.exp(-0.5 * axis * axis)
        wavelet = wavelet - np.mean(wavelet)
        norm = float(np.linalg.norm(wavelet))
        if norm > 0:
            wavelet = wavelet / (norm * sqrt(float(scale)))
        coefficients.append(np.convolve(signal, wavelet[::-1], mode="same").astype(np.float32))
    return np.log1p(np.abs(np.stack(coefficients))).astype(np.float32)


def _normalize_image(image: NDArray[np.float32]) -> NDArray[np.float32]:
    finite = image[np.isfinite(image)]
    if finite.size == 0:
        return np.zeros_like(image, dtype=np.float32)
    low = float(np.percentile(finite, 1))
    high = float(np.percentile(finite, 99))
    if high <= low:
        return np.zeros_like(image, dtype=np.float32)
    return cast(NDArray[np.float32], np.clip((image - low) / (high - low), 0.0, 1.0))


def _last_conv_layer(model: Any, torch: Any) -> Any:
    convolution = torch.nn.Conv2d
    for module in reversed(tuple(model.modules())):
        if isinstance(module, convolution):
            return module
    raise RuntimeError("no convolutional target layer is available for Grad-CAM")


def _gradcam_array(activation: Any, gradient: Any, torch: Any) -> NDArray[np.float32]:
    weights = gradient.mean(dim=(2, 3), keepdim=True)
    cam = torch.relu((weights * activation).sum(dim=1))[0]
    cam = cam - cam.min()
    maximum = cam.max()
    if float(maximum.detach().cpu()) > 0:
        cam = cam / maximum
    return np.asarray(cam.detach().cpu().numpy(), dtype=np.float32)


def _jet_colormap(normalized: NDArray[np.float32]) -> NDArray[np.uint8]:
    x = np.clip(normalized, 0.0, 1.0)
    red = np.clip(1.5 - np.abs(4.0 * x - 3.0), 0.0, 1.0)
    green = np.clip(1.5 - np.abs(4.0 * x - 2.0), 0.0, 1.0)
    blue = np.clip(1.5 - np.abs(4.0 * x - 1.0), 0.0, 1.0)
    return (np.stack([red, green, blue], axis=-1) * 255).astype(np.uint8)


def _draw_centered_title(draw: Any, text: str, left: int, width: int, y: int) -> None:
    try:
        bbox = draw.textbbox((0, 0), text)
        text_width = bbox[2] - bbox[0]
    except AttributeError:
        text_width = len(text) * 7
    draw.text((left + max(0, (width - text_width) // 2), y), text, fill=(26, 32, 44))


def _as_gray_rgb(image: Any, size: tuple[int, int]) -> Any:
    from PIL import Image

    gray = image.convert("L").resize(size, Image.Resampling.BICUBIC)
    return Image.merge("RGB", (gray, gray, gray))


def _heatmap_panel(
    heatmap: NDArray[np.float32],
    size: tuple[int, int],
) -> tuple[Any, NDArray[np.uint8]]:
    from PIL import Image

    heatmap_image = Image.fromarray(
        (np.clip(heatmap, 0.0, 1.0) * 255).astype(np.uint8),
        mode="L",
    ).resize(size, Image.Resampling.BICUBIC)
    heatmap_values = np.asarray(heatmap_image, dtype=np.float32) / 255.0
    heat_rgb = _jet_colormap(heatmap_values)
    return Image.fromarray(heat_rgb, mode="RGB"), heat_rgb


def _blend_overlay(base_rgb: Any, heat_rgb: NDArray[np.uint8], alpha: float = 0.45) -> Any:
    from PIL import Image

    base = np.asarray(base_rgb, dtype=np.float32) / 255.0
    heat = heat_rgb.astype(np.float32) / 255.0
    overlay = np.clip((1.0 - alpha) * base + alpha * heat, 0.0, 1.0)
    return Image.fromarray((overlay * 255).astype(np.uint8), mode="RGB")


def _gradcam_overlay_png(image: Any, heatmap: NDArray[np.float32], target_label: str) -> bytes:
    from PIL import Image, ImageDraw

    panel_size = (512, 512)
    title_height = 46
    margin = 16
    gap = 26
    original_panel = _as_gray_rgb(image, panel_size)
    heat_panel, heat_rgb = _heatmap_panel(heatmap, panel_size)
    overlay_panel = _blend_overlay(original_panel, heat_rgb, alpha=0.45)
    canvas_width = margin * 2 + panel_size[0] * 3 + gap * 2
    canvas_height = title_height + panel_size[1] + margin
    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")
    draw = ImageDraw.Draw(canvas)
    panels = (
        ("Original CWT grid", original_panel),
        (f"Heatmap for {_safe_text(target_label, 32)}", heat_panel),
        ("Overlay", overlay_panel),
    )
    for index, (title, panel) in enumerate(panels):
        left = margin + index * (panel_size[0] + gap)
        _draw_centered_title(draw, title, left, panel_size[0], 14)
        canvas.paste(panel, (left, title_height))
    output = BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()


def _dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        cleaned = _safe_text(value)
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return tuple(result)


def _safe_text(value: str, limit: int = 240) -> str:
    compact = " ".join(value.split())
    return compact[:limit]
