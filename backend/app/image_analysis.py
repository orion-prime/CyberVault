from pathlib import Path
from PIL import Image, ImageChops, ImageEnhance, ExifTags
import io
import numpy as np
import cv2
from skimage.metrics import structural_similarity


def _open_image(path: Path):
    try:
        image = Image.open(path)
        image.load()
        return image
    except Exception as exc:
        raise ValueError(f"Unsupported or unreadable image: {exc}") from exc


def _exif_summary(image):
    raw = image.getexif()
    result = {}
    for key, value in raw.items():
        name = ExifTags.TAGS.get(key, str(key))
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        result[name] = str(value)[:300]
    return result


def _ela_score(path: Path):
    # ELA is a visual triage heuristic for JPEGs, not proof of editing.
    try:
        with Image.open(path) as original:
            if original.format != "JPEG":
                return None
            buffer = io.BytesIO()
            original.convert("RGB").save(buffer, "JPEG", quality=90)
            buffer.seek(0)
            recompressed = Image.open(buffer).convert("RGB")
            difference = ImageChops.difference(original.convert("RGB"), recompressed)
            enhanced = ImageEnhance.Brightness(difference).enhance(4.0)
            values = np.asarray(enhanced, dtype=np.float32)
            return round(float(values.mean()), 3)
    except Exception:
        return None



def _to_data_url(image: Image.Image, max_side: int = 1100) -> str:
    image = image.copy().convert("RGB")
    image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=82, optimize=True)
    import base64
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _visual_artifacts(original_path: Path, candidate_path: Path):
    """Create bounded side-by-side, difference heatmap and blended overlay previews."""
    with Image.open(original_path) as original_file:
        original = original_file.convert("RGB")
    with Image.open(candidate_path) as candidate_file:
        candidate = candidate_file.convert("RGB")

    # Normalize candidate to original dimensions for direct visual comparison.
    candidate_aligned = candidate.resize(original.size, Image.Resampling.LANCZOS) if candidate.size != original.size else candidate
    max_side = 900
    original.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    candidate_aligned.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    # Match final sizes in case thumbnail rounding differs.
    if candidate_aligned.size != original.size:
        candidate_aligned = candidate_aligned.resize(original.size, Image.Resampling.LANCZOS)

    a = np.asarray(original, dtype=np.int16)
    b = np.asarray(candidate_aligned, dtype=np.int16)
    diff = np.max(np.abs(a - b), axis=2).astype(np.uint8)

    # Contrast-enhanced heatmap: brighter regions indicate larger pixel differences.
    heat = np.clip(diff.astype(np.float32) * 3.0, 0, 255).astype(np.uint8)
    heat_rgb = np.zeros((*heat.shape, 3), dtype=np.uint8)
    heat_rgb[..., 0] = heat
    heat_rgb[..., 1] = np.clip(heat.astype(np.float32) * 0.22, 0, 255).astype(np.uint8)
    heatmap = Image.fromarray(heat_rgb, mode="RGB")

    overlay = Image.blend(original, candidate_aligned, alpha=0.5)
    canvas = Image.new("RGB", (original.width * 2, original.height), "white")
    canvas.paste(original, (0, 0))
    canvas.paste(candidate_aligned, (original.width, 0))

    return {
        "side_by_side_data_url": _to_data_url(canvas),
        "heatmap_data_url": _to_data_url(heatmap),
        "overlay_data_url": _to_data_url(overlay),
        "preview_note": "Candidate is resized to the original dimensions for visual alignment. Heatmap brightness represents pixel difference, not proof of editing."
    }


def compare_images(original_path: Path, candidate_path: Path):
    original = _open_image(original_path)
    candidate = _open_image(candidate_path)

    original_exif = _exif_summary(original)
    candidate_exif = _exif_summary(candidate)
    exif_changes = [
        {"field": key, "original": original_exif.get(key), "uploaded": candidate_exif.get(key)}
        for key in sorted(set(original_exif) | set(candidate_exif))
        if original_exif.get(key) != candidate_exif.get(key)
    ]

    dimensions = {
        "original": list(original.size),
        "uploaded": list(candidate.size),
        "match": original.size == candidate.size,
    }
    formats = {"original": original.format, "uploaded": candidate.format}

    # Compare images at a common size to allow a useful similarity estimate even
    # when dimensions differ. Resizing itself is reported as a limitation.
    a = original.convert("RGB")
    b = candidate.convert("RGB")
    if a.size != b.size:
        b = b.resize(a.size, Image.Resampling.LANCZOS)

    a_np = np.asarray(a)
    b_np = np.asarray(b)
    gray_a = cv2.cvtColor(a_np, cv2.COLOR_RGB2GRAY)
    gray_b = cv2.cvtColor(b_np, cv2.COLOR_RGB2GRAY)
    ssim = float(structural_similarity(gray_a, gray_b, data_range=255))
    mean_abs_diff = float(np.mean(np.abs(a_np.astype(np.float32) - b_np.astype(np.float32))))
    changed_ratio = float(np.mean(np.any(a_np != b_np, axis=2)))

    ela_original = _ela_score(original_path)
    ela_candidate = _ela_score(candidate_path)

    # Conservative categories: image pixel difference is flagged for review;
    # metadata-only change is low. These thresholds are prototype heuristics.
    pixel_changed = ssim < 0.995 or mean_abs_diff > 1.0
    if pixel_changed:
        classification, severity = "IMAGE_CONTENT_DIFFERENCE", "MEDIUM"
        explanation = (
            "The uploaded image differs at the pixel level from the collected image. "
            "This can result from editing, resizing, recompression, colour changes or other processing; "
            "the difference is not proof of manipulation."
        )
    elif exif_changes or formats["original"] != formats["uploaded"]:
        classification, severity = "IMAGE_METADATA_ONLY", "LOW"
        explanation = "The decoded image pixels are highly similar, but image metadata or format differs."
    else:
        classification, severity = "IMAGE_NO_DIFFERENCE_DETECTED", "LOW"
        explanation = "No material pixel or available EXIF metadata difference was detected by this prototype."

    visual_comparison = _visual_artifacts(original_path, candidate_path)

    return {
        "visual_comparison": visual_comparison,
        "classification": classification,
        "severity": severity,
        "explanation": explanation,
        "dimensions": dimensions,
        "formats": formats,
        "similarity_ssim": round(ssim, 5),
        "mean_absolute_pixel_difference": round(mean_abs_diff, 4),
        "changed_pixel_ratio": round(changed_ratio, 5),
        "exif_changes": exif_changes,
        "ela_mean_original": ela_original,
        "ela_mean_uploaded": ela_candidate,
        "ela_note": "ELA is reported only as an investigative JPEG heuristic; values are not a standalone tampering verdict.",
        "limitations": [
            "SSIM and pixel differences detect visual changes but cannot establish intent or authenticity.",
            "Resizing, recompression, rotation, colour correction and format conversion can create differences.",
            "EXIF metadata may be absent, stripped or edited.",
            "ELA is JPEG-specific and can produce misleading patterns; visual and contextual human review is required."
        ],
    }
