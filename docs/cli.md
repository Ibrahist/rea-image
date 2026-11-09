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
- `--vlm MODEL`: Vision-Language Model identifier for semantic review (e.g., `gemini-1.5-pro`, `gpt-4o`).
- `--agent-review`: Export inspection tasks and crops formatted for AI coding agent inspection.

---

### `report`
Rebuilds the interactive `report.html` from an existing `report.json`:
```bash
rea-image report <out_dir>
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
Extracts embedded prompts or builds a reverse-engineered prompt with variants:
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

### `eval`
Executes the evaluation benchmark harness against a labeled dataset:
```bash
rea-image eval [dataset_path]
```
Generates `RESULTS.md` with area-weighted accuracy and calibration tracking across clean originals, compressed files, and screenshots.

