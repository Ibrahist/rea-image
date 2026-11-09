"""Image loading, format validation, orientation normalization, and preview generation."""

from dataclasses import dataclass
from pathlib import Path
from typing import Union
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from rea_image.config import settings
from rea_image.schemas import ImageMetadata
from rea_image.ingest.metadata_extractor import extract_metadata


class IngestError(Exception):
    """Raised when an image cannot be ingested or is out of scope."""
    pass


class AnimatedImageError(IngestError):
    """Raised when an animated image is provided."""
    pass


@dataclass
class IngestResult:
    path: Path
    file_size_bytes: int
    metadata: ImageMetadata
    rgb_image: Image.Image
    rgb_array: np.ndarray
    preview: Image.Image
    raw_info: dict


def check_animation(img: Image.Image, file_path: Path) -> None:
    """Check if the image is animated and raise AnimatedImageError if so."""
    fmt = (img.format or file_path.suffix.lstrip(".")).upper()
    
    if fmt == "GIF":
        raise AnimatedImageError(f"Animated files are out of scope: Animated GIF detected in '{file_path.name}'.")
        
    is_animated = getattr(img, "is_animated", False)
    n_frames = getattr(img, "n_frames", 1)
    
    if is_animated or n_frames > 1:
        if fmt == "WEBP":
            raise AnimatedImageError(f"Animated files are out of scope: Animated WebP detected in '{file_path.name}'.")
        elif fmt == "PNG":
            raise AnimatedImageError(f"Animated files are out of scope: Animated PNG (APNG) detected in '{file_path.name}'.")
        else:
            raise AnimatedImageError(f"Animated files are out of scope: Multi-frame/animated {fmt} detected in '{file_path.name}'.")


def load_image(file_path: Union[str, Path]) -> IngestResult:
    """Load image safely without modifying the source file.
    
    Validates format, checks for animated files, normalizes EXIF orientation,
    converts to working RGB array, and produces a downscaled preview.
    """
    path = Path(file_path)
    if not path.exists():
        raise IngestError(f"File not found: {path}")
    if not path.is_file():
        raise IngestError(f"Path is not a regular file: {path}")

    ext = path.suffix.lower()
    if ext == ".gif":
        raise AnimatedImageError(f"Animated files are out of scope: Animated GIF detected in '{path.name}'.")

    if ext not in settings.supported_extensions:
        raise IngestError(
            f"Unsupported format '{ext}'. Supported formats: {', '.join(sorted(settings.supported_extensions))}"
        )

    file_size = path.stat().st_size
    if file_size == 0:
        raise IngestError(f"File is empty (0 bytes): {path}")

    # Register HEIF / AVIF decoders if requested and available
    if ext in (".heic", ".heif"):
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            raise IngestError(
                f"Cannot decode HEIC image '{path.name}': pillow-heif is not installed. "
                "Install it with: pip install 'rea-image[heic]'"
            )
    elif ext == ".avif":
        try:
            import pillow_heif
            pillow_heif.register_avif_opener()
        except (ImportError, AttributeError):
            try:
                import pillow_avif  # noqa: F401
            except ImportError:
                pass

    # Support large photographic files safely
    Image.MAX_IMAGE_PIXELS = 200_000_000

    try:
        with Image.open(path) as img:
            check_animation(img, path)
            
            # Preserve raw info dictionary (contains EXIF, PNG chunks, etc.)
            raw_info = dict(img.info)
            
            # Huge image handling: if pixels > max_image_pixels, process with memory-efficient preview
            total_px = img.width * img.height
            if total_px > settings.max_image_pixels:
                # Downsample large images for working memory safety
                scale = (settings.max_image_pixels / float(total_px)) ** 0.5
                target_size = (int(img.width * scale), int(img.height * scale))
                working_copy = img.resize(target_size, Image.Resampling.BOX)
            else:
                working_copy = img.copy()

            # Normalize EXIF orientation without altering the original file
            try:
                normalized_img = ImageOps.exif_transpose(working_copy)
            except Exception:
                normalized_img = working_copy

            if normalized_img is None:
                normalized_img = working_copy

    except (AnimatedImageError, IngestError):
        raise
    except UnidentifiedImageError as e:
        if ext in (".heic", ".heif"):
            raise IngestError(
                f"Cannot decode HEIC image '{path.name}': pillow-heif is not installed or the file is corrupted. "
                "Install with: pip install 'rea-image[heic]'"
            ) from e
        if ext == ".avif":
            raise IngestError(
                f"Cannot decode AVIF image '{path.name}': pillow-heif/pillow-avif is not installed or the file is corrupted. "
                "Install with: pip install 'rea-image[avif]'"
            ) from e
        raise IngestError(f"Corrupt or unrecognized image file '{path.name}': {e}") from e
    except Exception as e:
        raise IngestError(f"Failed to open image '{path.name}': {e}") from e

    # Extract metadata before color conversion
    metadata = extract_metadata(normalized_img, path)

    # Convert to working RGB representation
    if normalized_img.mode != "RGB":
        rgb_image = normalized_img.convert("RGB")
    else:
        rgb_image = normalized_img

    rgb_array = np.asarray(rgb_image, dtype=np.uint8)

    # Generate downscaled preview for model calls and visual inspector
    w, h = rgb_image.size
    max_dim = settings.preview_max_dim
    if max(w, h) > max_dim:
        scale = max_dim / float(max(w, h))
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        preview = rgb_image.resize(new_size, Image.Resampling.LANCZOS)
    else:
        preview = rgb_image.copy()

    return IngestResult(
        path=path,
        file_size_bytes=file_size,
        metadata=metadata,
        rgb_image=rgb_image,
        rgb_array=rgb_array,
        preview=preview,
        raw_info=raw_info,
    )
