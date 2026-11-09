"""rea-image Quickstart Demo

This script demonstrates how to use rea-image programmatically to:
1. Synthesize a sample test image (with background, text, and subject layers)
2. Run the full reverse-engineering analysis pipeline
3. Inspect the resulting verdict, evidence, and recreation blueprints
"""

import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

from rea_image.report.orchestrator import run_analysis_pipeline


def create_demo_image(output_path: Path) -> Path:
    """Generate a sample composite image with gradient background, a circular patch, and vector text."""
    width, height = 800, 600
    
    # Create smooth gradient background
    y_coords = np.linspace(0, 1, height)[:, None]
    x_coords = np.linspace(0, 1, width)[None, :]
    
    r = (30 + 120 * x_coords).astype(np.uint8)
    g = (40 + 80 * y_coords).astype(np.uint8)
    b = (100 + 100 * (x_coords + y_coords) / 2).astype(np.uint8)
    
    rgb = np.stack([r + np.zeros((height, width), dtype=np.uint8),
                    g + np.zeros((height, width), dtype=np.uint8),
                    b + np.zeros((height, width), dtype=np.uint8)], axis=-1)
    
    img = Image.fromarray(rgb)
    draw = ImageDraw.Draw(img)
    
    # Draw a simulated subject shape
    draw.ellipse([300, 180, 500, 380], fill=(220, 160, 60), outline=(255, 200, 100), width=4)
    
    # Draw vector typography
    draw.text((250, 440), "REA-IMAGE DEMO", fill=(255, 255, 255))
    draw.text((270, 480), "Reverse-Engineering Visuals", fill=(200, 230, 255))
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    return output_path


def main():
    print("=" * 60)
    print("rea-image Programmatic Quickstart Demo")
    print("=" * 60)
    
    work_dir = Path("./demo_output")
    demo_image = work_dir / "demo_sample.png"
    
    print(f"\n[1] Creating sample image at: {demo_image}")
    create_demo_image(demo_image)
    
    print("\n[2] Executing rea-image analysis pipeline (offline mode)...")
    report = run_analysis_pipeline(
        image_path=demo_image,
        out_dir=work_dir / "analysis_results",
        offline=True,
    )
    
    print("\n[3] Analysis Results:")
    print(f"  • Verdict: {report.verdict.summary}")
    print(f"  • Overall Confidence: {report.verdict.confidence}")
    print(f"  • Regions Segmented: {len(report.regions)}")
    
    print("\n[4] Identified Layers / Regions:")
    for region in report.regions:
        print(f"  - Region {region.id} ({region.label}): {region.method} ({region.area_pct:.1f}% area)")
    
    print("\n[5] Global Craft Analysis:")
    if report.global_analysis.palette:
        palette_hexes = [c.hex for c in report.global_analysis.palette]
        print(f"  • Dominant Palette: {', '.join(palette_hexes)}")
    if report.global_analysis.lighting:
        lighting_setup = report.global_analysis.lighting.get("setup", "N/A")
        print(f"  • Lighting Setup: {lighting_setup}")
        
    print("\n[6] Recreation Plan:")
    for region in report.regions:
        print(f"  • Region {region.id} [{region.recreate.path.upper()}]: est {region.recreate.est_time}, cost {region.recreate.est_cost}")
        if region.recreate.starter_files:
            print(f"    Starter files: {', '.join(region.recreate.starter_files)}")
        
    results_dir = work_dir / "analysis_results"
    print("\n[7] Exported Artifacts:")
    print(f"  • verdict.txt:   {results_dir / 'verdict.txt'}")
    print(f"  • report.json:   {results_dir / 'report.json'}")
    print(f"  • report.html:   {results_dir / 'report.html'}")
    print(f"  • layers/:       {results_dir / 'layers'}")
    print(f"  • recreate/:     {results_dir / 'recreate'}")
    
    print("\nDemo completed successfully! Open report.html in any browser to inspect interactively.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
