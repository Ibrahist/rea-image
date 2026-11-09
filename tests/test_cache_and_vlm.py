"""Tests for disk caching and VLM client offline safeguards."""

from pathlib import Path
from PIL import Image
from rea_image.cache import PipelineCache
from rea_image.evidence.vlm_client import VLMClient


def test_pipeline_cache(tmp_path: Path):
    """Test setting, getting, and clearing cache entries by image SHA-256."""
    cache = PipelineCache(cache_dir=tmp_path / "cache", enabled=True)
    sha = "a1b2c3d4e5f67890" * 4

    # Miss on empty cache
    assert cache.get(sha, "step1") is None

    # Set and retrieve
    payload = {"verdict": "real photograph", "confidence": "high"}
    cache.set(sha, "step1", payload)
    cached = cache.get(sha, "step1")
    assert cached == payload

    # Clear cache
    cache.clear()
    assert cache.get(sha, "step1") is None


def test_vlm_client_offline_safeguard():
    """Verify VLM client never attempts network calls in offline mode."""
    client = VLMClient(offline=True, api_key="mock_key")
    assert client.is_available() is False

    img = Image.new("RGB", (64, 64), color=(100, 100, 100))
    res = client.analyze_visual_semantics(img)
    assert res is None


def test_vlm_client_missing_key():
    """Verify VLM client reports unavailable if no API key or endpoint configured."""
    client = VLMClient(offline=False, api_key=None, endpoint=None)
    assert client.is_available() is False


def test_orchestrator_cache_plumbing(tmp_path: Path):
    """Verify that run_analysis_pipeline leverages and populates default_cache."""
    from rea_image.report.orchestrator import run_analysis_pipeline
    from rea_image.cache import default_cache

    img_path = tmp_path / "cache_sample.png"
    img = Image.new("RGB", (80, 80), color=(150, 150, 150))
    img.save(img_path)

    out1 = tmp_path / "out1"
    report1 = run_analysis_pipeline(img_path, out_dir=out1)
    sha256 = report1.image.sha256

    # Verify cached intermediate entries exist
    cached_craft = default_cache.get(sha256, "craft_analysis")
    assert cached_craft is not None
    assert "palette" in cached_craft

    # Re-run pipeline and verify it completes using cache
    out2 = tmp_path / "out2"
    report2 = run_analysis_pipeline(img_path, out_dir=out2)
    assert report2.verdict.summary == report1.verdict.summary

