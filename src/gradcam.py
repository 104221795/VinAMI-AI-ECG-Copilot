from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image


def find_target_layer(model: torch.nn.Module) -> torch.nn.Module:
    try:
        return model.stages[-1].blocks[-1].conv_dw
    except Exception:
        pass
    last_conv = None
    for module in model.modules():
        if isinstance(module, torch.nn.Conv2d):
            last_conv = module
    if last_conv is None:
        raise RuntimeError("Could not find a Conv2d layer for Grad-CAM.")
    return last_conv


class GradCAM:
    def __init__(self, model: torch.nn.Module, target_layer: torch.nn.Module):
        self.model = model
        self.target_layer = target_layer
        self.activations = None
        self.gradients = None
        self._handles = [
            target_layer.register_forward_hook(self._forward_hook),
            target_layer.register_full_backward_hook(self._backward_hook),
        ]

    def _forward_hook(self, module, inputs, output):
        self.activations = output.detach()

    def _backward_hook(self, module, grad_input, grad_output):
        self.gradients = grad_output[0].detach()

    def remove(self) -> None:
        for handle in self._handles:
            handle.remove()

    def __call__(self, input_tensor: torch.Tensor, class_idx: int) -> np.ndarray:
        self.model.zero_grad(set_to_none=True)
        logits = self.model(input_tensor)
        score = logits[:, class_idx].sum()
        score.backward()
        if self.activations is None or self.gradients is None:
            raise RuntimeError("Grad-CAM hooks did not capture activations/gradients.")
        weights = self.gradients.mean(dim=(2, 3), keepdim=True)
        cam = (weights * self.activations).sum(dim=1, keepdim=False)
        cam = torch.relu(cam)[0].detach().cpu().numpy()
        cam -= cam.min()
        max_value = cam.max()
        if max_value > 0:
            cam /= max_value
        return cam


def overlay_cam(image: Image.Image, cam: np.ndarray, alpha: float = 0.42) -> tuple[np.ndarray, np.ndarray]:
    original = np.array(image.convert("RGB"))
    cam_resized = cv2.resize(cam, (original.shape[1], original.shape[0]))
    heatmap = cv2.applyColorMap(np.uint8(255 * cam_resized), cv2.COLORMAP_JET)
    heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
    overlay = np.uint8((1 - alpha) * original + alpha * heatmap)
    return heatmap, overlay


def generate_gradcam(model: torch.nn.Module, input_tensor: torch.Tensor, original_image: Image.Image, class_idx: int, device: str | torch.device = "cpu") -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    target_layer = find_target_layer(model)
    cam_runner = GradCAM(model, target_layer)
    try:
        cam = cam_runner(input_tensor.to(device), class_idx)
    finally:
        cam_runner.remove()
    heatmap, overlay = overlay_cam(original_image, cam)
    return cam, heatmap, overlay


def save_overlay(path: Path, overlay: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(overlay).save(path)

