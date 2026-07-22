"""
Image replacement module with metadata inheritance.
Prizma Studio - Smart Image Replacement
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional, Tuple
from PIL import Image, ImageOps
import io

# Type aliases
ResizeMode = Literal["fit", "fill", "stretch", "match_original"]


class ImageMetadata:
    """Stores complete metadata of an image."""
    
    def __init__(self, image_path: str | Path):
        self.path = Path(image_path)
        
        with Image.open(self.path) as img:
            self.size = img.size  # (width, height)
            self.mode = img.mode  # RGB, RGBA, CMYK, L, etc.
            self.format = img.format  # PNG, JPEG, TIFF, etc.
            self.dpi = img.info.get("dpi", (72, 72))  # (x_dpi, y_dpi)
            
            # For JPEG: quality and subsampling
            self.quality = 95  # default
            self.subsampling = 0  # default
            
            if self.format == "JPEG":
                # Try to detect quality from quantization tables
                try:
                    qtables = getattr(img, "quantization", None)
                    if qtables:
                        # Estimate quality from quantization table
                        self.quality = self._estimate_jpeg_quality(img)
                except:
                    pass
            
            # Store other format-specific info
            self.info = img.info.copy()
    
    @staticmethod
    def _estimate_jpeg_quality(img: Image.Image) -> int:
        """Estimate JPEG quality from quantization tables."""
        # This is a simplified estimation
        # Real quality detection is complex and not always accurate
        try:
            qtables = img.quantization
            if qtables and len(qtables) > 0:
                # Average the quantization values
                avg_quant = sum(sum(row) for row in qtables[0]) / (8 * 8)
                # Rough estimation: lower quant = higher quality
                if avg_quant < 10:
                    return 95
                elif avg_quant < 20:
                    return 85
                elif avg_quant < 40:
                    return 75
                else:
                    return 65
        except:
            pass
        return 85  # default
    
    def __repr__(self) -> str:
        return (
            f"ImageMetadata(size={self.size}, mode={self.mode}, "
            f"format={self.format}, dpi={self.dpi})"
        )


def resize_with_mode(
    img: Image.Image,
    target_size: Tuple[int, int],
    mode: ResizeMode,
    no_upscale: bool = True
) -> Image.Image:
    """
    Resize image according to specified mode.
    
    Args:
        img: Source PIL Image
        target_size: (width, height) target dimensions
        mode: Resize strategy
            - "fit": Fit inside target, preserve aspect ratio, add padding
            - "fill": Fill target, preserve aspect ratio, crop excess
            - "stretch": Stretch to exact target size
            - "match_original": Same as stretch for this function
        no_upscale: If True, don't upscale smaller images
    
    Returns:
        Resized PIL Image
    """
    target_w, target_h = target_size
    src_w, src_h = img.size
    
    # Check if upscaling is disabled
    if no_upscale and src_w <= target_w and src_h <= target_h and mode != "stretch":
        return img.copy()
    
    if mode == "stretch" or mode == "match_original":
        # Simple resize to exact dimensions
        return img.resize(target_size, Image.Resampling.LANCZOS)
    
    elif mode == "fit":
        # Fit inside target, preserve aspect ratio
        img_copy = img.copy()
        img_copy.thumbnail(target_size, Image.Resampling.LANCZOS)
        
        # Create new image with target size and paste centered
        result = Image.new(img.mode, target_size, color=(255, 255, 255))
        
        # Calculate position to center the image
        paste_x = (target_w - img_copy.width) // 2
        paste_y = (target_h - img_copy.height) // 2
        
        result.paste(img_copy, (paste_x, paste_y))
        return result
    
    elif mode == "fill":
        # Fill target, crop excess, preserve aspect ratio
        src_aspect = src_w / src_h
        target_aspect = target_w / target_h
        
        if src_aspect > target_aspect:
            # Source is wider, scale by height
            new_h = target_h
            new_w = int(new_h * src_aspect)
        else:
            # Source is taller, scale by width
            new_w = target_w
            new_h = int(new_w / src_aspect)
        
        # Resize to calculated dimensions
        img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Crop to target size (center crop)
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        right = left + target_w
        bottom = top + target_h
        
        return img_resized.crop((left, top, right, bottom))
    
    else:
        raise ValueError(f"Unknown resize mode: {mode}")


def replace_matching(
    original_path: str | Path,
    new_path: str | Path,
    output_path: str | Path,
    mode: ResizeMode = "match_original",
    no_upscale: bool = True,
    inherit_metadata: bool = True
) -> ImageMetadata:
    """
    Replace image with metadata inheritance.
    
    Args:
        original_path: Path to original image (source of metadata)
        new_path: Path to new image (will be transformed)
        output_path: Where to save result
        mode: Resize mode (fit/fill/stretch/match_original)
        no_upscale: Don't upscale if new image is smaller
        inherit_metadata: Apply original's metadata to result
    
    Returns:
        ImageMetadata of the result
    """
    # Read original metadata
    orig_meta = ImageMetadata(original_path)
    
    # Open new image
    with Image.open(new_path) as new_img:
        # Convert to original's color mode if needed
        if inherit_metadata and new_img.mode != orig_meta.mode:
            try:
                new_img = new_img.convert(orig_meta.mode)
            except Exception as e:
                # Some conversions might fail, log and continue
                print(f"Warning: Could not convert {new_img.mode} to {orig_meta.mode}: {e}")
        
        # Resize according to mode
        if mode == "match_original" or inherit_metadata:
            # Force exact size match
            result_img = resize_with_mode(
                new_img, 
                orig_meta.size, 
                "match_original",
                no_upscale=no_upscale
            )
        else:
            result_img = resize_with_mode(
                new_img,
                orig_meta.size,
                mode,
                no_upscale=no_upscale
            )
        
        # Prepare save parameters
        save_kwargs = {}
        
        if inherit_metadata:
            # Apply DPI
            save_kwargs["dpi"] = orig_meta.dpi
            
            # Apply format
            output_format = orig_meta.format or "PNG"
            
            # Format-specific parameters
            if output_format == "JPEG":
                save_kwargs["quality"] = orig_meta.quality
                save_kwargs["optimize"] = True
                save_kwargs["subsampling"] = orig_meta.subsampling
            
            elif output_format == "PNG":
                save_kwargs["optimize"] = True
                # Copy PNG-specific info if available
                if "transparency" in orig_meta.info:
                    save_kwargs["transparency"] = orig_meta.info["transparency"]
            
            elif output_format == "TIFF":
                # Copy TIFF compression if available
                if "compression" in orig_meta.info:
                    save_kwargs["compression"] = orig_meta.info["compression"]
        else:
            # Use new image's format
            output_format = Image.open(new_path).format or "PNG"
        
        # Save result
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        result_img.save(
            output_path,
            format=output_format,
            **save_kwargs
        )
    
    # Return metadata of saved image
    return ImageMetadata(output_path)


def get_metadata_comparison(
    original_path: str | Path,
    new_path: str | Path
) -> dict:
    """
    Compare metadata between original and new image.
    Useful for preview/debugging.
    
    Returns:
        Dictionary with comparison data
    """
    orig_meta = ImageMetadata(original_path)
    new_meta = ImageMetadata(new_path)
    
    return {
        "original": {
            "size": orig_meta.size,
            "mode": orig_meta.mode,
            "format": orig_meta.format,
            "dpi": orig_meta.dpi,
            "quality": orig_meta.quality if orig_meta.format == "JPEG" else None
        },
        "new": {
            "size": new_meta.size,
            "mode": new_meta.mode,
            "format": new_meta.format,
            "dpi": new_meta.dpi,
            "quality": new_meta.quality if new_meta.format == "JPEG" else None
        },
        "differences": {
            "size_match": orig_meta.size == new_meta.size,
            "mode_match": orig_meta.mode == new_meta.mode,
            "format_match": orig_meta.format == new_meta.format,
            "dpi_match": orig_meta.dpi == new_meta.dpi
        }
    }


# Convenience function for quick testing
def quick_replace(original: str, new: str, output: str, mode: str = "match_original"):
    """Quick replace with default settings."""
    result = replace_matching(original, new, output, mode=mode)
    print(f"✓ Replaced: {output}")
    print(f"  Size: {result.size}, Mode: {result.mode}, DPI: {result.dpi}")
    return result


if __name__ == "__main__":
    # Example usage / testing
    print("Image Replace Module - Prizma Studio")
    print("=" * 50)
    print("\nUsage example:")
    print(">>> from modules.image_replace import replace_matching")
    print(">>> replace_matching('original.jpg', 'new.png', 'output.jpg')")
