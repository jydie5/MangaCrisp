from __future__ import annotations

import hashlib
from collections.abc import Iterable

from PIL import Image, ImageStat

from mangacrisp_app.capture.models import CapturePage, CaptureWarning

MIN_CAPTURE_DIMENSION = 64
BLACK_MEAN_THRESHOLD = 2.0
BLACK_EXTREMA_THRESHOLD = 8
NEAR_DUPLICATE_DISTANCE = 5


def image_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def perceptual_dhash(image: Image.Image) -> str:
    grayscale = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    values = list(grayscale.get_flattened_data())
    bits = 0
    for row in range(8):
        offset = row * 9
        for column in range(8):
            bits = (bits << 1) | int(values[offset + column] > values[offset + column + 1])
    return f"{bits:016x}"


def hamming_distance(left: str, right: str) -> int:
    if not left or not right:
        return 64
    return (int(left, 16) ^ int(right, 16)).bit_count()


def frame_warnings(image: Image.Image) -> list[CaptureWarning]:
    warnings: list[CaptureWarning] = []
    if image.width < MIN_CAPTURE_DIMENSION or image.height < MIN_CAPTURE_DIMENSION:
        warnings.append(CaptureWarning("too_small", "撮影画像が極端に小さいため確認してください。"))
    rgba = image.convert("RGBA")
    alpha_extrema = rgba.getchannel("A").getextrema()
    if alpha_extrema == (0, 0):
        warnings.append(CaptureWarning("transparent", "撮影画像が完全に透明です。"))
    rgb = rgba.convert("RGB")
    mean = sum(ImageStat.Stat(rgb).mean) / 3
    extrema = max(channel[1] for channel in rgb.getextrema())
    if mean <= BLACK_MEAN_THRESHOLD and extrema <= BLACK_EXTREMA_THRESHOLD:
        warnings.append(CaptureWarning("black", "撮影画像が黒一色に見えます。"))
    return warnings


def duplicate_warnings(
    sha256: str,
    perceptual_hash: str,
    pages: Iterable[CapturePage],
    *,
    exclude_position: int | None = None,
) -> list[CaptureWarning]:
    warnings: list[CaptureWarning] = []
    for page in pages:
        if exclude_position is not None and page.position == exclude_position:
            continue
        if page.sha256 == sha256:
            return [CaptureWarning("duplicate", "以前のページと完全に同じ画像です。")]
        if hamming_distance(page.perceptual_hash, perceptual_hash) <= NEAR_DUPLICATE_DISTANCE:
            warnings.append(CaptureWarning("near_duplicate", "以前のページと似た画像です。"))
            break
    return warnings
