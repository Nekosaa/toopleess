"""Image processing utilities with smart resizing"""
from PIL import Image, ImageFilter
from pathlib import Path
import logging
from dataclasses import dataclass
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

@dataclass
class ImageMetadata:
    """Store image metadata for preservation"""
    dpi: Tuple[int, int] = (72, 72)
    format: str = "PNG"
    jpeg_quality: int = 95

    @classmethod
    def from_image(cls, img: Image.Image):
        """Extract metadata from PIL Image"""
        return cls(
            dpi=img.info.get('dpi', (72, 72)),
            format=img.format or "PNG",
            jpeg_quality=img.info.get('quality', 95)
        )


def prepare_for_smart_object(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """
    ФИКС 3: Режим COVER для Smart Objects - заполняем весь кадр с обрезкой.
    
    Масштабирует изображение так, чтобы оно ЗАПОЛНИЛО весь кадр target_w x target_h,
    обрезает излишки по центру. Результат: ТОЧНО target_w x target_h БЕЗ пустот.
    
    Args:
        img: Source PIL Image
        target_w: Target width in pixels
        target_h: Target height in pixels
    
    Returns:
        Image with EXACT dimensions, covering entire frame (cropped if needed)
    """
    orig_w, orig_h = img.size
    target_ratio = target_w / target_h
    orig_ratio = orig_w / orig_h
    
    # COVER mode: масштабируем так, чтобы заполнить весь кадр
    # Выбираем бОльший коэффициент масштабирования
    scale = max(target_w / orig_w, target_h / orig_h)
    
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)
    
    # Resize с высоким качеством
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Обрезаем до точного размера (центрирование)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    
    # Crop гарантирует ТОЧНЫЕ размеры
    final = resized.crop((left, top, left + target_w, top + target_h))
    
    logger.info(f"✅ Smart Object COVER: {orig_w}x{orig_h} → scale x{scale:.2f} → crop to {target_w}x{target_h}")
    
    return final


def resize_with_mode(
    img: Image.Image,
    target_width: int,
    target_height: int,
    mode: str = "fill",
    no_upscale: bool = False
) -> Image.Image:
    """Resize image with various modes

    Args:
        img: Source PIL Image
        target_width: Target width in pixels
        target_height: Target height in pixels
        mode: Resize mode - 'fit', 'fill', 'cover', 'stretch'
        no_upscale: If True, never upscale (only downscale)

    Returns:
        Resized PIL Image
    """
    orig_w, orig_h = img.size
    target_ratio = target_width / target_height
    orig_ratio = orig_w / orig_h

    logger.info(f"Resize: {orig_w}x{orig_h} → {target_width}x{target_height} (mode={mode}, no_upscale={no_upscale})")

    # Calculate scale factor
    if mode == "fill":
        # Fill entire frame (may crop)
        scale = max(target_width / orig_w, target_height / orig_h)
    elif mode == "fit":
        # Fit inside frame (may have gaps)
        scale = min(target_width / orig_w, target_height / orig_h)
    elif mode == "cover":
        # Cover entire area (alias for fill)
        scale = max(target_width / orig_w, target_height / orig_h)
    elif mode == "stretch":
        # Stretch to exact size (may distort)
        new_w, new_h = target_width, target_height
        return img.resize((new_w, new_h), Image.LANCZOS)
    else:
        raise ValueError(f"Unknown resize mode: {mode}")

    # Apply no_upscale constraint
    if no_upscale and scale > 1.0:
        logger.warning(f"⚠ Upscale blocked: x{scale:.2f} (no_upscale=True)")
        scale = 1.0

    # Log upscale warning
    if scale > 2.0:
        logger.warning(f"⚠ High upscale: x{scale:.1f} - качество может снизиться")

    # Resize with high-quality LANCZOS resampling
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)
    resized = img.resize((new_w, new_h), Image.LANCZOS)

    # Crop to exact target size if needed (for fill/cover modes)
    if mode in ["fill", "cover"]:
        left = (new_w - target_width) // 2
        top = (new_h - target_height) // 2
        resized = resized.crop((left, top, left + target_width, top + target_height))

    return resized


def prepare_image_for_psd(
    source_path: str,
    target_width: int,
    target_height: int,
    output_path: str,
    mode: str = "fill",
    no_upscale: bool = False,
    force_fill: bool = False
) -> ImageMetadata:
    """Prepare image for PSD replacement

    Args:
        source_path: Path to source image
        target_width: Target width in pixels
        target_height: Target height in pixels
        output_path: Path to save prepared image
        mode: Resize mode (ignored if force_fill=True)
        no_upscale: Prevent upscaling (ignored if force_fill=True)
        force_fill: Force fill mode with upscale (for Smart Objects)

    Returns:
        ImageMetadata object with original metadata
    """
    # FIX БАГ 1: force_fill для Smart Objects
    if force_fill:
        effective_mode = "cover"
        effective_no_upscale = False
        logger.info("🔧 force_fill=True: игнорируем UI настройки, используем fill+upscale")
    else:
        effective_mode = mode
        effective_no_upscale = no_upscale

    # Load source image
    img = Image.open(source_path)
    metadata = ImageMetadata.from_image(img)

    # Convert to RGB if needed
    if img.mode not in ['RGB', 'RGBA']:
        img = img.convert('RGB')

    orig_w, orig_h = img.size
    scale = max(target_width / orig_w, target_height / orig_h) if effective_mode == "fill" else min(target_width / orig_w, target_height / orig_h)

    # Warn about small sources
    if orig_w < 200 or orig_h < 200:
        logger.warning(f"⚠ Исходник мал: {orig_w}x{orig_h}px - рекомендуется >200px")

    # Log upscale coefficient
    if scale > 1.0 and not effective_no_upscale:
        logger.warning(f"⚠ Upscale x{scale:.1f}: исходник {orig_w}x{orig_h} мал для {target_width}x{target_height}")

    # Resize image
    resized = resize_with_mode(img, target_width, target_height, effective_mode, effective_no_upscale)
    
    # УЛУЧШЕНИЕ 4: Sharpening при upscale
    if scale > 1.3 and not effective_no_upscale:
        try:
            # Более агрессивный sharpen для сильного upscale
            resized = resized.filter(
                ImageFilter.UnsharpMask(radius=2.0, percent=140, threshold=2)
            )
            logger.info(f"✅ Applied aggressive sharpening (upscale x{scale:.1f})")
        except Exception as e:
            logger.warning(f"⚠ Sharpening failed: {e}")
    
    # УЛУЧШЕНИЕ 4: DPI нормализация
    max_side = max(target_width, target_height)
    if max_side > 2000:
        resized.info['dpi'] = (300, 300)
        logger.info("✅ Set DPI to 300 (high-res output)")
    else:
        resized.info['dpi'] = (72, 72)
        logger.info("✅ Set DPI to 72 (web resolution)")

    # Save with metadata preservation
    save_kwargs = {'dpi': resized.info.get('dpi', (72, 72))}
    if metadata.format == 'JPEG':
        save_kwargs['quality'] = metadata.jpeg_quality

    resized.save(output_path, **save_kwargs)
    logger.info(f"✅ Saved: {output_path} ({resized.size[0]}x{resized.size[1]}px)")

    return metadata
