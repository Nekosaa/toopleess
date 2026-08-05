"""Image processing utilities with smart resizing (DPI-aware)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
import logging

from PIL import Image, ImageFilter

logger = logging.getLogger(__name__)


@dataclass
class ImageMetadata:
    dpi: Tuple[int, int] = (72, 72)
    format: str = "PNG"
    jpeg_quality: int = 95

    @classmethod
    def from_image(cls, img: Image.Image) -> "ImageMetadata":
        return cls(
            dpi=img.info.get("dpi", (72, 72)),
            format=img.format or "PNG",
            jpeg_quality=img.info.get("quality", 95),
        )


# ---------------------------------------------------------------------------
# Core resize
# ---------------------------------------------------------------------------
def resize_with_mode(
    img: Image.Image,
    target_w: int,
    target_h: int,
    mode: str = "fill",
    no_upscale: bool = False,
) -> Image.Image:
    """
    Resize с одним из режимов:
      fit     - вписать целиком (могут быть поля)
      fill    - заполнить кадр с обрезкой центра (COVER)
      cover   - alias for fill
      stretch - растянуть точно (искажает пропорции)
    """
    orig_w, orig_h = img.size
    logger.info(
        f"Resize: {orig_w}x{orig_h} -> {target_w}x{target_h} "
        f"(mode={mode}, no_upscale={no_upscale})"
    )

    if mode == "stretch":
        return img.resize((target_w, target_h), Image.LANCZOS)

    if mode in ("fill", "cover"):
        scale = max(target_w / orig_w, target_h / orig_h)
    elif mode == "fit":
        scale = min(target_w / orig_w, target_h / orig_h)
    else:
        raise ValueError(f"Unknown resize mode: {mode}")

    if no_upscale and scale > 1.0:
        logger.warning(f"Upscale blocked (no_upscale=True): x{scale:.2f}")
        scale = 1.0

    if scale > 2.0:
        logger.warning(f"High upscale x{scale:.1f} - quality may drop")

    new_w = max(1, int(round(orig_w * scale)))
    new_h = max(1, int(round(orig_h * scale)))
    resized = img.resize((new_w, new_h), Image.LANCZOS)

    if mode in ("fill", "cover"):
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        resized = resized.crop((left, top, left + target_w, top + target_h))

    return resized


def prepare_for_smart_object(
    img: Image.Image, target_w: int, target_h: int
) -> Image.Image:
    """COVER: заполнить кадр с обрезкой центра. Ровно target_w x target_h."""
    return resize_with_mode(img, target_w, target_h, mode="cover", no_upscale=False)


# ---------------------------------------------------------------------------
# Full pipeline: file in -> prepared file out
# ---------------------------------------------------------------------------
def prepare_image_for_psd(
    source_path: str,
    target_width: int,
    target_height: int,
    output_path: str,
    mode: str = "fill",
    no_upscale: bool = False,
    force_fill: bool = False,
    doc_dpi: Optional[Tuple[int, int]] = None,
    mild_sharpen: bool = True,
) -> ImageMetadata:
    """
    Готовим картинку под конкретный размер (внутренний размер SO).

    Args:
        source_path : путь к исходнику
        target_width/height : размер, к которому приводим (внутренний PSB SO!)
        output_path : куда сохранить
        mode : fit / fill / cover / stretch
        no_upscale : не увеличивать сверх 1x
        force_fill : принудительно cover (для SO чтоб не было пустот)
        doc_dpi : DPI родительского PSD — наследуем, чтоб PS не пересчитал размер
        mild_sharpen : мягкий unsharp только при сильном upscale
    """
    effective_mode = "cover" if force_fill else mode
    effective_no_upscale = False if force_fill else no_upscale
    if force_fill:
        logger.info("force_fill=True -> cover, upscale allowed")

    img = Image.open(source_path)
    metadata = ImageMetadata.from_image(img)

    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    orig_w, orig_h = img.size
    if orig_w < 200 or orig_h < 200:
        logger.warning(f"Source is small: {orig_w}x{orig_h}px (recommend >200)")

    if effective_mode in ("fill", "cover"):
        scale = max(target_width / orig_w, target_height / orig_h)
    elif effective_mode == "fit":
        scale = min(target_width / orig_w, target_height / orig_h)
    else:
        scale = 1.0

    resized = resize_with_mode(
        img, target_width, target_height, effective_mode, effective_no_upscale
    )

    # МЯГКИЙ шарп только если реально сильный апскейл
    if mild_sharpen and scale > 1.5 and not effective_no_upscale:
        try:
            resized = resized.filter(
                ImageFilter.UnsharpMask(radius=1.0, percent=60, threshold=3)
            )
            logger.info(f"Mild unsharp applied (upscale x{scale:.2f})")
        except Exception as e:
            logger.warning(f"Sharpening failed: {e}")

    # ГЛАВНОЕ: наследуем DPI из PSD-документа (или из исходника)
    if doc_dpi and doc_dpi[0] > 0 and doc_dpi[1] > 0:
        out_dpi = doc_dpi
    else:
        out_dpi = metadata.dpi or (72, 72)
    resized.info["dpi"] = out_dpi
    logger.info(f"Output DPI set to {out_dpi}")

    save_kwargs = {"dpi": out_dpi}
    ext = Path(output_path).suffix.lower()
    if ext in (".jpg", ".jpeg"):
        save_kwargs["quality"] = metadata.jpeg_quality

    resized.save(output_path, **save_kwargs)
    logger.info(f"Saved: {output_path} ({resized.size[0]}x{resized.size[1]}px)")
    return metadata
