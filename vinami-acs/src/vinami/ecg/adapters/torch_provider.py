"""Optional ConvNeXtV2 research adapter; model frameworks remain below the port."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Any

from vinami.ecg.ports.provider import (
    AIProviderHealth,
    ECGExplanationRequest,
    ECGExplanationResult,
    ECGPredictionRequest,
    ECGPredictionResult,
    InputValidationResult,
    ModelInfo,
)


class TorchConvNeXtV2Provider:
    """Load a verified research checkpoint once when the optional runtime is configured."""

    def __init__(self, checkpoint: Path, expected_checksum: str, device: str = "cpu") -> None:
        self._checkpoint = checkpoint
        self._expected_checksum = expected_checksum.lower()
        self._device_name = device
        self._model: Any = None
        self._metadata: dict[str, Any] | None = None

    def get_model_info(self) -> ModelInfo:
        metadata = self._load_metadata()
        return ModelInfo(
            name=str(metadata["config"]["model_name"]),
            version=f"checkpoint-epoch-{metadata['epoch']}",
            provider_name="torch-convnextv2-research",
            input_contract="224x224 RGB CWT 12-lead grid",
            synthetic=False,
            checkpoint_checksum=self._expected_checksum,
            label_order=tuple(str(item) for item in metadata["label_names"]),
            threshold_source="checkpoint validation metadata",
        )

    def health(self) -> AIProviderHealth:
        try:
            self._verify_file()
            import timm  # noqa: F401
            import torch  # noqa: F401
        except Exception as error:
            return AIProviderHealth(
                False, "torch-convnextv2-research", f"unavailable: {type(error).__name__}"
            )
        return AIProviderHealth(
            True, "torch-convnextv2-research", "checkpoint and optional runtime are available"
        )

    def validate_input(self, request: ECGPredictionRequest) -> InputValidationResult:
        if request.input_quality in {"poor", "insufficient", "unsupported", "failed"}:
            return InputValidationResult(
                False, failure_reason="technical ECG quality blocks analysis"
            )
        if request.image_bytes is None:
            return InputValidationResult(
                False, failure_reason="verified CWT image bytes are required"
            )
        return InputValidationResult(True)

    def predict(self, request: ECGPredictionRequest) -> ECGPredictionResult:
        validation = self.validate_input(request)
        if not validation.valid:
            raise ValueError(validation.failure_reason)
        model, metadata, torch = self._load_model()
        from PIL import Image
        from torchvision import transforms

        started_at = datetime.now(UTC)
        started = perf_counter()
        image = Image.open(BytesIO(request.image_bytes or b"")).convert("RGB")
        tensor = (
            transforms.Compose(
                [
                    transforms.Resize((224, 224)),
                    transforms.ToTensor(),
                    transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
                ]
            )(image)
            .unsqueeze(0)
            .to(self._device_name)
        )
        with torch.inference_mode():
            values = torch.sigmoid(model(tensor))[0].detach().cpu().tolist()
        labels = tuple(str(item) for item in metadata["label_names"])
        thresholds = {str(key): float(value) for key, value in metadata["threshold"].items()}
        scores = dict(zip(labels, (float(value) for value in values), strict=True))
        completed_at = datetime.now(UTC)
        return ECGPredictionResult(
            request.study_id,
            str(metadata["config"]["model_name"]),
            f"checkpoint-epoch-{metadata['epoch']}",
            "torch-convnextv2-research",
            started_at,
            completed_at,
            request.input_quality,
            scores,
            thresholds,
            tuple(label for label in labels if scores[label] >= thresholds[label]),
            (),
            (f"Inference duration {round((perf_counter() - started) * 1000)} ms.",),
            {"checkpoint_sha256": self._expected_checksum, "device": self._device_name},
            None,
            False,
        )

    def explain(self, request: ECGExplanationRequest) -> ECGExplanationResult:
        return ECGExplanationResult(
            request.study_id,
            request.target_label,
            "unavailable",
            "A verified Grad-CAM runtime adapter is not configured.",
            synthetic=False,
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
                num_classes=len(metadata["label_names"]),
            )
            model.load_state_dict(metadata["model_state_dict"], strict=True)
            model.to(self._device_name).eval()
            self._model = model
        return self._model, metadata, torch
