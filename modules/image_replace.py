"""
Image replacement module with metadata inheritance.
Prizma Studio - Smart Image Replacement
v2 - fixed: no more tiny image in center, defaults to fill.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional, Tuple
from PIL import Image

ResizeMode = Literal["fit", "fill", "stretch", "match_original", "cover"]


class ImageMetadata:
    """Stores complete metadata of an image."""

    def __init__(self, image_path: str | Path):
        self.path = Path(image_path)
        with Image.open(self.path) as img:
            self.size = img.size
            self.mode = img.mode
            self.format = img.format
            self.dpi = img.info.get("dpi", (72, 72))
            self.quality = 95
            self.subsampling = 0
            if self.format == "JPEG":
                try:
                    if getattr(img, "quantization", None):
                        self.quality = self._estimate_jpeg_quality(img)
                except Exception:
                    pass
            self.info = img.info.copy()

    @staticmethod
    def _estimate_jpeg_quality(img: Image.Image) -> int:
        try:
            qtables = img.quantization
            if qtables and len(qtables) > 0:
                first = qtables[list(qtables.keys())[0]] if isinstance(qtables, dict) else qtables[0]
                if isinstance(first, (list, tuple)):
                    flat = []
                    for row in first:
                        if isinstance(row, (list, tuple)):
                            flat.extend(row)
                        else:
                            flat.append(row)
                    avg = sum(flat) / max(len(flat), 1)
                    if avg < 10: return 95
                    if avg < 20: return 85
                    if avg < 40: return 75
                    return 65
        except Exception:
            pass
        return 85

    def __repr__(self) -> str:
        return f"ImageMetadata(size={self.size}, mode={self.mode}, format={self.format}, dpi={self.dpi})"


def resize_with_mode(
    img: Image.Image,
    target_size: Tuple[int, int],
    mode: ResizeMode = "fill",
    no_upscale: bool = False,
) -> Image.Image:
    """
    Resize image to target_size.

    Modes:
      - "fill" / "cover"   : preserve aspect, fill entire target, crop excess (RECOMMENDED default)
      - "fit"              : preserve aspect, fit inside, transparent padding (RGBA)
      - "stretch" / "match_original" : ignore aspect, exact target size

    no_upscale=False by default — small source will be scaled UP to fit target.
    """
    target_w, target_h = int(target_size[0]), int(target_size[1])
    if target_w <= 0 or target_h <= 0:
        return img.copy()

    src_w, src_h = img.size

    # No-upscale guard (rarely used; off by default now)
    if no_upscale and src_w <= target_w and src_h <= target_h and mode not in ("stretch", "match_original"):
        return img.copy()

    if mode in ("stretch", "match_original"):
        return img.resize((target_w, target_h), Image.Resampling.LANCZOS)

    if mode in ("fill", "cover"):
        src_aspect = src_w / src_h
        target_aspect = target_w / target_h
        if src_aspect > target_aspect:
            new_h = target_h
            new_w = max(1, int(round(new_h * src_aspect)))
        else:
            new_w = target_w
            new_h = max(1, int(round(new_w / src_aspect)))
        img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        return img_resized.crop((left, top, left + target_w, top + target_h))

    if mode == "fit":
        img_copy = img.copy()
        img_copy.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
        # Transparent RGBA canvas — no more white borders!
        if img_copy.mode != "RGBA":
            img_copy = img_copy.convert("RGBA")
        result = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        px = (target_w - img_copy.width) // 2
        py = (target_h - img_copy.height) // 2
        result.paste(img_copy, (px, py), img_copy)
        return result

    raise ValueError(f"Unknown resize mode: {mode}")


def replace_matching(
    original_path: str | Path,
    new_path: str | Path,
    output_path: str | Path,
    mode: ResizeMode = "fill",
    no_upscale: bool = False,
    inherit_metadata: bool = True,
) -> ImageMetadata:
    """
    Replace image, inheriting metadata (size/dpi/format) from original.
    Default mode is 'fill' — output visually matches the original slot perfectly.
    """
    orig_meta = ImageMetadata(original_path)

    with Image.open(new_path) as new_img:
        new_img.load()

        target_size = orig_meta.size
        result_img = resize_with_mode(new_img, target_size, mode=mode, no_upscale=no_upscale)

        if inherit_metadata and result_img.mode != orig_meta.mode:
            try:
                if orig_meta.mode == "RGB" and result_img.mode == "RGBA":
                    bg = Image.new("RGB", result_img.size, (255, 255, 255))
                    bg.paste(result_img, mask=result_img.split()[-1])
                    result_img = bg
                else:
                    result_img = result_img.convert(orig_meta.mode)
            except Exception as e:
                print(f"[image_replace] mode convert warn: {e}")

        save_kwargs = {}
        output_format = orig_meta.format if inherit_metadata else (Image.open(new_path).format or "PNG")
        if not output_format:
            output_format = "PNG"

        if inherit_metadata:
            save_kwargs["dpi"] = orig_meta.dpi
            if output_format == "JPEG":
                save_kwargs["quality"] = orig_meta.quality
                save_kwargs["optimize"] = True
                save_kwargs["subsampling"] = orig_meta.subsampling
                if result_img.mode in ("RGBA", "LA", "P"):
                    result_img = result_img.convert("RGB")
            elif output_format == "PNG":
                save_kwargs["optimize"] = True

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result_img.save(output_path, format=output_format, **save_kwargs)

    return ImageMetadata(output_path)


def get_metadata_comparison(original_path, new_path) -> dict:
    a = ImageMetadata(original_path)
    b = ImageMetadata(new_path)
    return {
        "original": {"size": a.size, "mode": a.mode, "format": a.format, "dpi": a.dpi},
        "new":      {"size": b.size, "mode": b.mode, "format": b.format, "dpi": b.dpi},
        "differences": {
            "size_match": a.size == b.size,
            "mode_match": a.mode == b.mode,
            "format_match": a.format == b.format,
            "dpi_match": a.dpi == b.dpi,
        },
    }
