"""Pytest configuration and test fixture generators."""

import os
from pathlib import Path
from PIL import Image, ImageDraw
import pytest


@pytest.fixture(autouse=True, scope="session")
def isolate_test_cache(tmp_path_factory):
    """Isolate rea-image disk cache to a temporary directory per pytest session."""
    temp_cache = tmp_path_factory.mktemp("rea_image_test_cache")
    os.environ["REA_IMAGE_CACHE_DIR"] = str(temp_cache)
    from rea_image.config import settings
    from rea_image.cache import default_cache
    settings.cache_dir = temp_cache
    default_cache.cache_dir = temp_cache
    default_cache.enabled = True
    yield temp_cache


@pytest.fixture
def fixtures_dir(tmp_path: Path) -> Path:
    """Create directory containing test fixture images."""
    fix_dir = tmp_path / "fixtures"
    fix_dir.mkdir(parents=True, exist_ok=True)
    return fix_dir


@pytest.fixture
def sample_png(fixtures_dir: Path) -> Path:
    """Create a standard static RGB PNG."""
    img_path = fixtures_dir / "sample.png"
    img = Image.new("RGB", (320, 240), color=(73, 109, 137))
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 150, 150], fill=(255, 100, 100))
    draw.text((60, 60), "rea-image", fill=(255, 255, 255))
    img.save(img_path, format="PNG")
    return img_path


@pytest.fixture
def sample_jpeg(fixtures_dir: Path) -> Path:
    """Create a standard JPEG image."""
    img_path = fixtures_dir / "sample.jpg"
    img = Image.new("RGB", (400, 300), color=(200, 220, 240))
    draw = ImageDraw.Draw(img)
    draw.ellipse([80, 80, 220, 220], fill=(50, 120, 200))
    img.save(img_path, format="JPEG", quality=90)
    return img_path


@pytest.fixture
def animated_gif(fixtures_dir: Path) -> Path:
    """Create an animated multi-frame GIF."""
    img_path = fixtures_dir / "animated.gif"
    frame1 = Image.new("RGB", (100, 100), color=(255, 0, 0))
    frame2 = Image.new("RGB", (100, 100), color=(0, 255, 0))
    frame1.save(img_path, format="GIF", save_all=True, append_images=[frame2], loop=0, duration=100)
    return img_path


@pytest.fixture
def animated_webp(fixtures_dir: Path) -> Path:
    """Create an animated WebP image."""
    img_path = fixtures_dir / "animated.webp"
    frame1 = Image.new("RGB", (100, 100), color=(0, 0, 255))
    frame2 = Image.new("RGB", (100, 100), color=(255, 255, 0))
    frame1.save(img_path, format="WEBP", save_all=True, append_images=[frame2], loop=0, duration=100)
    return img_path

