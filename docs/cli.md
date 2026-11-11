# Command Line Interface (CLI) Reference

`rea-image` provides an expressive command-line interface powered by Typer and Rich.

---

## 1. Subcommands Overview

### `analyze`
Runs the complete reverse-engineering pipeline on an image or directory of images:
```bash
rea-image analyze <image_or_folder> [OPTIONS]
```
**Options**:
- `--out, -o PATH`: Output directory (defaults to `./rea_output/<image_name>`).
- `--offline / --online`: Force purely local offline execution without network calls (default: `--offline`).
- `--vlm MODEL`: Vision-Language Model identifier for visual review (e.g., `gemini-1.5-pro`, `gpt-4o`).
- `--agent-review`: Export inspection tasks and crops formatted for AI coding agent inspection.
- `--recursive, -r`: Recursively search folders for supported images.
- `--format, -f [table|json|csv]`: Set machine-readable stdout output format (default: `table`).
- `--jobs, -j N`: Set parallel worker count for multi-image folder runs (default: `1`).
  - *Concurrency Model*: Uses a thread pool (`concurrent.futures.ThreadPoolExecutor`). Heavy forensic compute kernels (NumPy 2D FFT, SciPy median filtering, Pillow image decoding) run in optimized C extensions that release Python's Global Interpreter Lock (GIL), yielding near-linear multi-core acceleration (benchmarking ~2.4x speedup on 14 dataset images) without the heavy multi-process spawn latency and pickle serialization overhead on Windows. Thread safety across parallel workers is guaranteed by atomic temporary file writes in `PipelineCache`.
- `--disable, -d DETECTOR`: Disable one or more specific detectors (e.g. `--disable frequency --disable noise`).
- `--open`: Open generated `report.html` in default web browser.

**Folder Runs Artifacts**:
When analyzing a folder of images, `rea-image` automatically exports a consolidated `batch_summary.csv` and cross-image consistency analysis.

---

### `explain`
Prints the exact weighted evidence ledger behind a verdict, showing each detector signal, weight multiplier, and net signed score contribution:
```bash
# Explain all regions
rea-image explain ./rea_output/my_sample

# Explain a specific region
rea-image explain ./rea_output/my_sample --region region_1
```

---

### `detectors`
Lists all registered built-in and third-party plugin detectors available in the registry:
```bash
rea-image detectors
```

---

### `report`
Rebuilds the interactive `report.html` from an existing `report.json`:
```bash
rea-image report <out_dir> [--open]
```

---

### `apply-review`
Applies agent or human visual review findings from `review_tasks.json` to resolve conflicts, updating `report.json`, `verdict.txt`, and `report.html`:
```bash
rea-image apply-review <out_dir> [--answers answers.json]
```

---

### `palette`
Extracts dominant color swatches, hex codes, RGB values, semantic roles, and grading metrics:
```bash
rea-image palette <image_path>
```

---

### `provenance`
Quickly inspects EXIF, XMP, IPTC, C2PA manifests, and AI generator metadata chunks:
```bash
rea-image provenance <image_path>
```

---

### `prompt`
Extracts embedded generation prompts or dynamic reverse-engineers a prompt using real image craft, camera, and lighting attributes:
```bash
rea-image prompt <image_path>
```

---

### `recreate`
Previews or dispatches the replication plan:
```bash
# Safe simulation (dry run)
rea-image recreate <out_dir> --dry-run

# Confirmed execution
rea-image recreate <out_dir> --confirm
```

---

### `camera`
Detects and inspects the physical or inferred camera hardware that captured an image:
```bash
# Display formatted terminal card with camera profile and optical diagnostics
rea-image camera <image_path>

# Output raw detected camera JSON schema
rea-image camera <image_path> --json
```
Extracts camera make, model, device classification (smartphone, mirrorless, DSLR, compact, drone, action camera), sensor format, lens model, aperture, shutter speed, ISO, and shooting parameters. If EXIF metadata was stripped, infers camera classification from aspect ratio constraints, depth of field, and computational unsharp masking halo forensics.

> **Note on Stripped-EXIF Inference**: Optical camera inference without EXIF is a best-effort diagnostic heuristic (measured benchmark accuracy: 100.0% on native sensor fixtures), not ground truth. The command outputs probabilistic candidate rankings (`candidates`) and defaults to "Inferred: Ambiguous Camera Profile" with low confidence when images are resized or evidence is mixed.

---

### `eval`
Executes the evaluation benchmark harness against a labeled dataset:
```bash
rea-image eval [dataset_path] [--tolerance 20.0]
```
Generates `RESULTS.md` with area-weighted accuracy and calibration tracking across clean originals, compressed files, and screenshots. Fails with exit code 1 if confidence bins deviate beyond `--tolerance`.
