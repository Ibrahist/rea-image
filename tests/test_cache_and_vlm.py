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
    # Cached keys include SHA256 and fingerprinted step names
    cached_craft = None
    for item in (default_cache.cache_dir / sha256[:2] / sha256[2:4]).glob(f"{sha256}_craft_*.json"):
        import json
        cached_craft = json.loads(item.read_text(encoding="utf-8"))
        break
    assert cached_craft is not None
    assert "palette" in cached_craft

    # Re-run pipeline and verify it completes using cache
    out2 = tmp_path / "out2"
    report2 = run_analysis_pipeline(img_path, out_dir=out2)
    assert report2.verdict.summary == report1.verdict.summary


def test_cache_version_invalidation(tmp_path: Path, monkeypatch):
    """Verify that changing package version invalidates stale cache entries."""
    from rea_image.report.orchestrator import run_analysis_pipeline
    import rea_image.report.orchestrator as orch

    img_path = tmp_path / "ver_sample.png"
    img = Image.new("RGB", (80, 80), color=(120, 140, 160))
    img.save(img_path)

    # 1. First run with current version
    rep1 = run_analysis_pipeline(img_path, out_dir=tmp_path / "v1")
    assert rep1 is not None

    # 2. Patch package version to mock upgrade
    monkeypatch.setattr(orch, "__version__", "99.0.0")

    # Run with different version should miss earlier cache tags
    sha256 = rep1.image.sha256
    v99_files_before = list((orch.default_cache.cache_dir / sha256[:2] / sha256[2:4]).glob(f"{sha256}_evidence_*.json"))

    rep2 = run_analysis_pipeline(img_path, out_dir=tmp_path / "v2")
    assert rep2 is not None

    v99_files_after = list((orch.default_cache.cache_dir / sha256[:2] / sha256[2:4]).glob(f"{sha256}_evidence_*.json"))
    # New cache entries under v99 tag must have been created
    assert len(v99_files_after) > len(v99_files_before)


def test_cache_offline_and_vlm_isolation(tmp_path: Path, monkeypatch):
    """Verify that an earlier offline run does not prevent subsequent VLM evaluation."""
    from rea_image.report.orchestrator import run_analysis_pipeline
    from rea_image.evidence.vlm_client import VLMClient

    img_path = tmp_path / "vlm_cache_test.png"
    img = Image.new("RGB", (80, 80), color=(200, 100, 50))
    img.save(img_path)

    # Step 1: Run offline
    rep_offline = run_analysis_pipeline(img_path, out_dir=tmp_path / "offline_run", offline=True)
    assert not any("vlm" in ev.name for ev in rep_offline.regions[0].evidence)

    # Mock VLMClient to be available and return pseudo-text anomaly
    monkeypatch.setattr(VLMClient, "is_available", lambda self: True)
    monkeypatch.setattr(
        VLMClient,
        "analyze_visual_semantics",
        lambda self, preview: {"text_gibberish": True, "anatomy_flaws": False},
    )

    # Step 2: Run online with VLM model specified
    rep_online = run_analysis_pipeline(img_path, out_dir=tmp_path / "online_run", offline=False, vlm_model="mock-gpt")
    
    # Must have called VLM and added VLM evidence despite prior offline run
    all_ev_names = [ev.name for ev in rep_online.regions[0].evidence]
    assert "vlm_pseudo_text_detected" in all_ev_names

