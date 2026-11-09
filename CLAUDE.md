# CLAUDE.md — rea-image Assistant Guidelines

## Build & Test Commands
- **Install package locally**: `pip install -e .`
- **Run all tests**: `pytest`
- **Run specific test suite**: `pytest tests/test_ingest.py -v`
- **Analyze image**: `python -m rea_image.cli analyze <path> [--out <dir>]`
- **Rebuild HTML report**: `python -m rea_image.cli report <out_dir>`
- **Apply agent review**: `python -m rea_image.cli apply-review <out_dir> [--answers <file>]`
- **Recreate dry-run**: `python -m rea_image.cli recreate <out_dir> --dry-run`

## Architecture Overview
- `rea_image/ingest/`: Image normalization, animation checks, format verification, dHash/pHash, and SHA-256.
- `rea_image/segment/`: Semantic region segmentation (classical fallback + SAM/VLM hook), OCR text merging.
- `rea_image/evidence/`: Typed evidence plugins (provenance, generator traces, ELA, noise, frequency 2D FFT, flat runs, visual checks, craft optics, lighting, palette, typography).
- `rea_image/judge/`: Weighted evidence engine (Provenance > Forensics > Visuals), conflict detection, and area-weighted aggregation.
- `rea_image/reverse/`: Layered prompts, ASCII lighting diagrams, 3D Blender scripts, SVG scaffolds, and HTML/CSS tokens.
- `rea_image/replicate/`: Cheapest viable path routing, batching logic, generation backend runner.
- `rea_image/capabilities/`: Data-driven `models.yaml` and `tools.yaml` capability matrix.
- `rea_image/report/`: Machine-readable `report.json`, interactive `report.html`, `verdict.txt`, and layer exports.

## Core Principles
1. **Evidence-First**: Never output certainty or ungrounded scores. Every conclusion must link directly to typed evidence.
2. **Deterministic-First**: Offline local tools run first; network calls (VLM/generation) are opt-in only.
3. **Transparent Contradictions**: Clashing signals trigger `needs_review` items rather than opaque guesses.
4. **Actionable Recreation**: Always output starter files to reproduce the image via the cheapest viable path.

