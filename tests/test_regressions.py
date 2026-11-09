"""Regression tests for outdoor photos, ELA calibration, FFT spectral peaks, conflict detection, and text segmentation."""

from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

from rea_image.ingest.loader import load_image
from rea_image.segment.classical import ClassicalSegmenter
from rea_image.evidence.forensics_jpeg import ForensicsJpegDetector
from rea_image.judge.conflict import ConflictDetector
from rea_image.report.orchestrator import run_analysis_pipeline
from rea_image.schemas import EvidenceItem, ProductionMethod


def create_outdoor_photo_fixture(path: Path) -> Path:
    """Create a realistic photo-like JPEG (2:3 ratio) simulating an outdoor animal photo with no EXIF and no text."""
    width, height = 400, 600
    
    # Natural gradient sky-to-ground backdrop
    y_coords = np.linspace(0, 1, height)[:, None]
    x_coords = np.linspace(0, 1, width)[None, :]
    
    # Sky blue transitioning to warm earth tones
    r = (120 + 80 * y_coords).astype(np.uint8)
    g = (150 + 40 * y_coords - 20 * x_coords).astype(np.uint8)
    b = (210 - 130 * y_coords).astype(np.uint8)
    
    base = np.stack([
        r + np.zeros((height, width), dtype=np.uint8),
        g + np.zeros((height, width), dtype=np.uint8),
        b + np.zeros((height, width), dtype=np.uint8),
    ], axis=-1)
    
    # Add subtle sensor-like Poisson noise
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 3.5, base.shape).astype(np.float32)
    noisy_base = np.clip(base.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    
    img = Image.fromarray(noisy_base)
    draw = ImageDraw.Draw(img)
    
    # Draw central organic textured subject (simulated animal / hen body & head)
    # Body
    draw.ellipse([120, 260, 300, 480], fill=(185, 95, 40))
    # Head and comb
    draw.ellipse([190, 150, 270, 270], fill=(195, 105, 50))
    draw.polygon([(220, 130), (240, 150), (210, 155)], fill=(220, 40, 30))  # red comb
    draw.polygon([(265, 200), (300, 215), (265, 225)], fill=(240, 190, 30))  # yellow beak
    
    # Fine textured strokes across body (simulating plumage / feathers)
    for _ in range(80):
        fx = rng.integers(140, 280)
        fy = rng.integers(270, 460)
        draw.line([(fx, fy), (fx + rng.integers(-8, 8), fy + rng.integers(-6, 6))], fill=(150, 75, 30), width=2)

    # Save as JPEG with standard quality (no EXIF metadata)
    img.save(path, format="JPEG", quality=88)
    return path


def test_outdoor_photo_not_vector_and_no_text_block(tmp_path: Path):
    """Regression test: Outdoor photo with no EXIF must not be classified as vector or contain text_blocks."""
    photo_path = tmp_path / "hen_outdoor.jpg"
    create_outdoor_photo_fixture(photo_path)
    
    out_dir = tmp_path / "hen_analysis"
    report = run_analysis_pipeline(
        image_path=photo_path,
        out_dir=out_dir,
        offline=True,
    )
    
    verdict_summary = report.verdict.summary.lower()
    
    # 1. Verdict must NOT be vector or graphic design
    assert "vector or graphic design" not in verdict_summary, f"Unexpected vector verdict: {report.verdict.summary}"
    assert "real photograph" in verdict_summary or "composite" in verdict_summary
    
    # 2. No region must be erroneously labeled as text_block
    region_labels = [r.label for r in report.regions]
    assert "text_block" not in region_labels, f"Erroneous text_block found in {region_labels}"
    assert "background" in region_labels
    assert "main_subject" in region_labels or "foreground_object" in region_labels


def test_ela_on_photo_is_neutral(tmp_path: Path):
    """Regression test: Low ELA error on continuous-tone photo must be neutral, not push vector design."""
    photo_path = tmp_path / "continuous_photo.jpg"
    create_outdoor_photo_fixture(photo_path)
    
    res = load_image(photo_path)
    detector = ForensicsJpegDetector()
    items = detector.run(res)
    
    # Must NOT emit ela_minimal_error supporting graphic design
    vector_ela = [
        it for it in items
        if it.name == "ela_minimal_error" and it.direction == ProductionMethod.GRAPHIC_DESIGN.value
    ]
    assert len(vector_ela) == 0, f"False vector ELA item generated: {vector_ela}"


def test_conflict_detection_when_optical_and_synthetic_coexist():
    """Regression test: Emits needs_review when natural optical signals meet synthetic indicators."""
    conflict_det = ConflictDetector()
    
    evidence = [
        EvidenceItem(
            name="jpeg_grid_aligned",
            value={"grid_detected": True},
            region="global",
            direction=ProductionMethod.REAL_PHOTO.value,
            strength=0.70,
            explanation="8x8 DCT grid aligned cleanly across boundaries",
        ),
        EvidenceItem(
            name="natural_frequency_falloff",
            value={"alpha": 1.95},
            region="global",
            direction=ProductionMethod.REAL_PHOTO.value,
            strength=0.75,
            explanation="Radial power spectrum follows natural scene statistics 1/f^1.95",
        ),
        EvidenceItem(
            name="spectral_peaks_upscaler",
            value={"peaks": 16},
            region="global",
            direction=ProductionMethod.AI_GENERATED.value,
            strength=0.35,
            explanation="Periodic upsampler peaks detected",
        ),
    ]
    
    contradictions, review_items = conflict_det.find_conflicts(evidence, region_id="r0")
    assert len(contradictions) >= 1
    assert len(review_items) >= 1
    assert any("conflict" in c.lower() for c in contradictions)
    assert any("agent" in r.question_for_agent.lower() or "inspect" in r.question_for_agent.lower() for r in review_items)


def test_segmentation_without_text_has_no_text_block():
    """Regression test: ClassicalSegmenter must never output a text_block region on textless images."""
    arr = np.zeros((300, 300, 3), dtype=np.uint8)
    # High-variance textured patch resembling plumage
    rng = np.random.default_rng(123)
    arr[50:180, 50:180] = rng.integers(50, 200, (130, 130, 3), dtype=np.uint8)
    
    segmenter = ClassicalSegmenter()
    regions = segmenter.segment(arr)
    
    labels = [r.label for r in regions]
    assert "text_block" not in labels


def test_tesseract_garbage_output_filtered(monkeypatch):
    """Regression test for A1: When Tesseract returns noisy low-confidence fragments, they must be rejected."""
    import pytesseract
    from rea_image.segment.ocr_merger import OCRTextDetector

    # Simulate tesseract image_to_data returning garbage words on photo texture
    garbage_data = {
        "text": ["", "es", "BA", "xs", "/-", "1"],
        "conf": ["-1", "42", "55", "30", "15", "50"],
    }
    monkeypatch.setattr(pytesseract, "image_to_data", lambda *args, **kwargs: garbage_data)

    detector = OCRTextDetector()
    arr = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
    boxes = detector.detect_text_boxes(arr)

    # All candidate boxes with garbage OCR text must be rejected
    assert len(boxes) == 0

    # Also verify that segmenter produces zero text_block regions
    segmenter = ClassicalSegmenter()
    regions = segmenter.segment(arr)
    assert not any(r.label == "text_block" for r in regions)


def test_composite_image_different_methods_per_region(tmp_path):
    """Regression test for A2: A composite image with photo half and flat graphic half must evaluate per-region."""
    photo_path = tmp_path / "base_photo.jpg"
    create_outdoor_photo_fixture(photo_path)
    photo_arr = np.array(Image.open(photo_path))

    # Top half: photo, Bottom half: flat vector/graphic design
    comp_arr = np.zeros_like(photo_arr)
    comp_arr[:300] = photo_arr[:300]
    comp_arr[300:] = [15, 25, 45]

    img = Image.fromarray(comp_arr)
    img_path = tmp_path / "composite.png"
    img.save(img_path)

    out_dir = tmp_path / "out"
    report = run_analysis_pipeline(img_path, out_dir, offline=True)

    assert len(report.regions) >= 2
    methods = {r.method for r in report.regions}
    # Expected: one region photo, one region vector/graphic
    assert ProductionMethod.GRAPHIC_DESIGN.value in methods
    assert ProductionMethod.REAL_PHOTO.value in methods
