![alt text](rea-image.png)

# rea-image

> Reverse-engineer any still image: deconstruct how it was made, present measurable evidence, and produce a blueprint to recreate it.
> 
> 🌐 **Interactive Web Guide & Live Showcase**: [rea-image.netlify.app](https://rea-image.netlify.app/)

`rea-image` is an open-source tool and AI agent skill to reverse-engineer still images. It analyzes an image or folder of images, classifies every layer/region into its true production method (real photograph, AI-generated, 3D render, graphic design, UI screenshot, illustration, or composite), backs every claim with hard provenance and forensic measurements, and generates actionable recreation blueprints via the cheapest viable path.

---

## Key Features

1. **Evidence-First Classification**:
   - **Hard Provenance**: C2PA Content Credentials manifests, EXIF/XMP/IPTC camera hardware data, AI generator PNG chunks (A1111/ComfyUI/Invoke/NovelAI/Midjourney), export software fingerprints.
   - **Digital Forensics**: Poisson-Gaussian residual noise modeling, Error Level Analysis (ELA), 8x8 JPEG DCT grid alignment, 2D FFT spectral peak detection, and flat-run vector analysis.
   - **Visual & Style Checks**: Plastic sheen detection, 3D shader analysis, and compression degradation penalty metrics.

2. **Semantic Region Decomposition**:
   - Splits images into semantic spatial regions (background, main subject, foreground objects, text blocks, UI cards).
   - Evaluates evidence per region and aggregates by area percentage.
   - Exports binary masks and image crops to `layers/`.

3. **Craft Deconstruction**:
   - **Camera & Lens**: Depth of field, aperture class (f/1.4 - f/16), focal length (wide, normal, telephoto), bokeh character, vignetting, chromatic aberration.
   - **Lighting Rigs**: Classifies illumination into 12 standard setups (Rembrandt, Butterfly, Split, Loop, Softbox, Window light, Ring light, Backlit, Golden hour, Hard flash, Neon, Overcast) with gear lists.
   - **Color Palette & Grading**: Dominant 5-6 color palette with semantic roles (`background`, `subject`, `accent`, `text`), dynamic range, and split-toning temperature.
   - **Typography & Grid**: Font family candidate ranking, hierarchy, weights, and layout grid tokens.

4. **Actionable Recreation Blueprints**:
   - **AI-Generated**: Layered prompts (faithful, simplified, style-transfer), negative prompts, aspect ratio, guidance scale, and sampler.
   - **Real Photography**: Physical shoot plan with camera settings, ASCII lighting diagram, gear list, and post-processing steps.
   - **3D Render**: Scene notes, PBR shader setups, and executable Blender 4.x Python starter script (`starter_scene.py`).
   - **Vector Graphic / UI**: Scalable SVG scaffold (`scaffold.svg`) and responsive HTML/CSS design tokens (`scaffold.html`).

5. **Self-Contained Interactive Report**:
   - Generates `report.html` featuring image inspection, region bounding box toggles, rule of thirds and golden ratio composition overlays, color swatches with click-to-copy hex codes, and "Needs Review" conflict warnings.

---

## Where This Tool Can Be Used

`rea-image` fits into practical production pipelines across creative, engineering, and investigative workflows:

| Sector / Role                  | Use Case / Environment                                          | Primary Deliverable                                 |
| :----------------------------- | :-------------------------------------------------------------- | :-------------------------------------------------- |
| **Designers & Art Directors**  | Moodboard deconstruction, style guides, poster vectorization    | Layered prompts, color roles, `scaffold.svg`        |
| **Photographers & Studios**    | Reverse-engineering lighting setups, matching client references | ASCII lighting diagram, gear list, `shoot_plan.md`  |
| **Frontend Engineers**         | Turning UI screenshots into responsive mockups & design tokens  | `scaffold.html`, CSS variables, font candidates     |
| **3D & Game Artists**          | Reverse-engineering environment lighting and shaders            | `starter_scene.py` (Blender Cycles rig & camera)    |
| **Trust, Safety & Journalism** | Image authenticity, C2PA validation, tamper/splice detection    | `verdict.txt`, ELA / noise forensics, `report.json` |
| **Marketing Teams**            | Multi-slide carousel audit, brand palette & tone continuity     | `consistency_summary.json` across image sets        |
| **Autonomous AI Agents**       | Multi-modal coding pipelines in Claude Code, Codex, Antigravity | `skills/rea-image/SKILL.md`, CLI integration        |

### Practical Workflow Scenarios

1. **Design & Creative Direction**:
   - **Moodboard & Reference Deconstruction**: Break client references and moodboards into concrete color roles (`background`, `accent`, `text`), lighting schemes, and composition rules.
   - **Prompt Engineering & Reverse Iteration**: Extract faithful, simplified, and style-transfer prompts from reference imagery to remix concepts in Midjourney, FLUX, or Stable Diffusion without guessing.
   - **Asset Scaffolding**: Automatically convert posters, banners, and vector assets into clean SVG layouts (`scaffold.svg`) and typography hierarchies.

2. **Photography & Studio Production**:
   - **Lighting & Shoot Reverse-Engineering**: Turn an editorial photo into a physical shoot plan with an ASCII lighting diagram, closest lighting setup (e.g., Rembrandt, Butterfly, Window Light), camera settings, and a recommended gear list.
   - **Color Grading & Look Replication**: Extract LUT-style color grading curves, dynamic range balance, and split-toning temperatures to match existing campaign photography.

3. **Frontend Engineering & UI/UX**:
   - **Screenshot to Code**: Convert UI mockups and web/app screenshots into responsive HTML/CSS structures (`scaffold.html`) with extracted design tokens (radii, type scales, spacing, color variables).
   - **Typography Audits**: Identify font candidates, text hierarchies, letter tracking, and layout grids directly from raster designs.

4. **3D Visualization & Game Art**:
   - **Render Inspection**: Determine whether a product or architectural image was generated in Blender, Unreal, or V-Ray via procedural shader falloffs and global illumination tells.
   - **Scaffold Generation**: Export a starter scene script (`starter_scene.py`) that sets up Blender Cycles with corresponding camera focal lengths, aspect ratios, and studio three-point lighting.

5. **Journalism, Fact-Checking & Trust & Safety**:
   - **C2PA & Provenance Verification**: Read cryptographic Content Credentials manifests, camera EXIF, and AI generator metadata chunks (A1111, ComfyUI, Midjourney).
   - **Forensic Tamper Detection**: Spot splicing, double-compression, DCT grid misalignment, and synthetic noise discrepancies between foreground subjects and backgrounds.
   - **Marketplace & E-commerce Verification**: Validate whether product listings are real physical photographs or synthetic AI/3D mockups.

6. **Marketing Campaigns & Series Consistency**:
   - **Multi-Slide & Carousel Auditing**: Run folder-level analysis on ad carousels and social series to verify cross-image color palette cohesion, lighting continuity, and aspect ratio alignment (`consistency_summary.json`).

7. **Autonomous AI Coding Agents**:
   - **Agent Tooling**: Integrated via `skills/rea-image/SKILL.md` into Claude Code, Codex, and Antigravity, allowing agents to autonomously analyze images, inspect region crops, and execute recreation workflows.

---

## Installation

Requirements: Python 3.10+ (tested on Python 3.10, 3.11, 3.12, 3.13, 3.14).

```bash
git clone https://github.com/Ibrahist/rea-image.git
cd rea-image

# Basic install
pip install -e .

# Optional extras:
pip install -e ".[ocr]"    # Tesseract OCR text extraction & typography measurement
pip install -e ".[heic]"   # Apple HEIC/HEIF image decoding
pip install -e ".[avif]"   # AVIF image decoding
pip install -e ".[vlm]"    # Optional Vision-Language Model semantic validation

# Full install with all extras & dev tools
pip install -e ".[ocr,heic,avif,vlm,dev]"
```

---

## Quick Start CLI

```bash
# Analyze a single image (offline by default)
rea-image analyze /path/to/image.png --out ./rea_output

# Analyze a directory in parallel with recursive scanning and machine-readable JSON output
rea-image analyze /path/to/folder --recursive --jobs 4 --format json

# Explain the evidence ledger and signed contribution behind a verdict
rea-image explain ./rea_output [--region region_1]

# List all available and pluggable evidence detectors
rea-image detectors

# Disable specific detectors during analysis
rea-image analyze /path/to/image.png --disable frequency,noise

# Analyze with Agent Review mode (exports crops and questions for review)
rea-image analyze /path/to/image.png --agent-review

# Apply agent or human review decisions to resolve conflicts
rea-image apply-review ./rea_output

# Rebuild interactive HTML report from report.json
rea-image report ./rea_output

# Extract palette and color grading only
rea-image palette /path/to/image.png

# Extract metadata, C2PA, and generator traces only
rea-image provenance /path/to/image.png

# Extract or reverse-engineer generation prompt
rea-image prompt /path/to/image.png

# Run dry-run recreation simulation
rea-image recreate ./rea_output --dry-run

# Run the evaluation benchmark harness (checks calibration tolerance)
rea-image eval eval/benchmark_data/dataset.json --tolerance 20.0
```

For complete command details and technical forensic limits, refer to [CLI Documentation](docs/cli.md) and [Technical Limitations](docs/limitations.md).

---

## Output Bundle

When you run `rea-image analyze`, the output folder contains:

```text
rea_output/
├── verdict.txt        # One-line summary (e.g. "AI-generated 78% + designed text 22%; Midjourney-style; 4:5; confidence medium-high")
├── report.json        # Full machine-readable schema (Section 7 specification)
├── report.html        # Self-contained interactive report with overlays, swatches, and prompts
├── original.png       # Normalized copy of the input image
├── layers/            # Exported region masks and crops
│   ├── region_0_mask.png
│   ├── region_0_crop.png
│   ├── region_1_mask.png
│   └── region_1_crop.png
└── recreate/          # Actionable starter files
    ├── prompt.txt         # Layered prompts and negative prompts
    ├── scaffold.svg       # Vector layout scaffold
    ├── scaffold.html      # Responsive UI component scaffold
    ├── shoot_plan.md      # Studio shoot plan with ASCII lighting diagram
    └── starter_scene.py   # Executable Blender Cycles Python scene
```

---

## Agent Integration (Claude Code, Antigravity, Codex)

`rea-image` is built agent-first. It includes native skill manifests and router instructions so AI coding assistants can install and execute image deconstruction autonomously.

### 1-Click / 1-Prompt Installation

You can install `rea-image` directly into your agent session using natural language:

```text
"Install https://github.com/Ibrahist/rea-image and break down this image: /path/to/image.png"
```

Or install the package in one command:

```bash
# Install in editable mode
pip install -e .

# Or directly from GitHub
pip install git+https://github.com/Ibrahist/rea-image.git

# Or with uv / pipx
uv pip install -e .
```

---

### Platform-Specific Setup

#### 1. Claude Code

`rea-image` provides a standard `.claude-plugin/plugin.json` manifest:

```bash
# Add as a local or remote plugin
claude plugin add ./rea-image
```

_Routing:_ Claude Code automatically reads `CLAUDE.md` and loads `skills/rea-image/SKILL.md`.

#### 2. Google Antigravity

The skill is located at `skills/rea-image/SKILL.md` and follows the Antigravity Customization standard.

- When opening this repository in Antigravity, the skill is automatically active.
- To use globally across all your workspaces:

  ```bash
  # Windows
  Copy-Item -Recurse skills/rea-image "$env:USERPROFILE\.gemini\antigravity\skills\"

  # Linux / macOS
  cp -r skills/rea-image ~/.gemini/antigravity/skills/
  ```

#### 3. OpenAI Codex & Cursor

Codex and Cursor automatically index `AGENTS.md` at the project root. When you attach or reference an image in chat, the agent uses the local CLI or Python module directly.

---

### Ready-to-Use Agent Prompts

Copy and paste any of these prompts into your agent chat:

- **Full Deconstruction & Recreate Plan**:
  > _"Break down this visual: how was it made, what is the evidence, and give me a step-by-step plan to recreate it: `./assets/banner.png`"_
- **Prompt & Style Reverse-Engineering**:
  > _"Reverse-engineer the generation prompt, lighting rig, and color grade for this image: `./assets/portrait.jpg`"_
- **Forensic Verification & Authenticity**:
  > _"Check whether this photo is authentic or AI-generated. Run digital forensics and inspect C2PA and EXIF data: `./assets/product.png`"_
- **Agent Visual Review Mode (Resolving Ambiguities)**:
  > _"Run `rea-image analyze ./assets/ambiguous.png --agent-review`. Inspect the exported region crops in `layers/`, resolve any questions in `needs_review`, and update the final verdict."_

---

## Documentation

- [Interactive Web Guide & Visual Showcase](https://rea-image.netlify.app/): Interactive online guide with live deconstruction demo, CLI runner, and architecture overview.
- [What It Detects](docs/what-it-detects.md): The 7 production methods, evidence weights, and detector details.
- [Decomposition Pipeline](docs/decompose.md): Ingest, semantic segmentation, craft extraction, and judgment.
- [Replication Blueprints](docs/replicate.md): Cheapest-viable-path routing, batching strategy, and prompt construction.
- [CLI Reference](docs/cli.md): Full subcommand documentation.
- [Ethics & Safety](docs/ethics.md): Responsible use guidelines and privacy commitments.
- [Evaluation & Benchmarks](eval/README.md): Methodology and empirical [RESULTS.md](eval/RESULTS.md).

---

## Ethics and Safety

- **Purpose**: Learn structure, lighting, and composition to recreate imagery with assets you have the right to use.
- **Probabilistic Evidence**: Classification is based on digital forensics and heuristic measurements, not infallible proof. Never use this tool to make personal accusations of fake imagery.
- **Privacy**: Fully functional offline. No images are uploaded to the cloud without explicit opt-in configuration. No facial identification or biometric recognition is performed.

---

## License

Apache-2.0 License. See [LICENSE](LICENSE) for details.
