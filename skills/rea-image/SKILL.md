---
name: rea-image
description: "Reverse-engineers any still image: deconstructs how it was made, presents measurable evidence, and generates an actionable recreation plan."
---

# rea-image Skill

Use this skill whenever you need to break down an image, inspect provenance or authenticity, analyze lighting and composition, or generate a blueprint to recreate it.

---

## When to Use This Skill
- The user provides an image or folder and asks: "How was this made?", "Is this AI or a photo?", "Extract the prompt/lighting for this image", or "Help me recreate this".
- The user wants a reverse prompt, photographic lighting diagram, SVG scaffold, or Blender scene based on an existing visual.

---

## Step-by-Step Workflow

### 1. Ingest & Inspect
Execute the analysis command in your workspace:
```bash
python -m rea_image.cli analyze "/path/to/image.png" --out "./rea_output"
```
If analyzing a directory of images:
```bash
python -m rea_image.cli analyze "/path/to/folder" --out "./rea_output"
```

### 2. Read the Generated Artifacts
Navigate to the specified output folder:
1. Read `verdict.txt` for the concise summary:
   ```text
   AI-generated 78% + designed text 22%; Midjourney-style; 4:5; confidence medium-high
   ```
2. Read `report.json` to inspect:
   - `verdict.method_breakdown`: Proportion of each medium (real photo, AI-generated, 3D render, graphic design, UI screenshot, illustration, composite).
   - `regions`: Bounding boxes, method classification, top supporting/contradicting evidence items.
   - `needs_review`: Conflicts identified by automated forensics that need your visual review.
   - `global`: Camera optics estimate, lighting setup, color palette, and composition.

### 3. Perform Agent Review (if `needs_review` is populated)
If `needs_review` contains entries:
1. Look at the region crops saved in `layers/<id>_crop.png`.
2. Inspect the specific question asked in `needs_review` (e.g. "Examine hand anatomy and hair-background transition to verify if camera EXIF is authentic or spoofed").
3. Use your visual reasoning to resolve the conflict and present a nuanced, honest explanation to the user.

### 4. Provide the Recreation Plan to the User
Present the recreation blueprint from `recreate/`:
- **AI-Generated**: Provide the faithful, simplified, and style-transfer prompts along with recommended settings (model, aspect ratio, guidance scale, sampler) from `recreate/prompt.txt`.
- **Real Photograph**: Provide the shoot plan, ASCII lighting diagram, gear list, and post-processing steps from `recreate/shoot_plan.md`.
- **Vector / Graphic**: Point to `recreate/scaffold.svg` or typography specs.
- **3D Render**: Point to `recreate/starter_scene.py`.
- **UI / Screenshot**: Point to `recreate/scaffold.html`.

---

## Targeted Subcommands

```bash
# Color palette and grading only
python -m rea_image.cli palette "/path/to/image.png"

# Provenance, EXIF, and AI generator chunks only
python -m rea_image.cli provenance "/path/to/image.png"

# Reverse-engineered prompt only
python -m rea_image.cli prompt "/path/to/image.png"

# Rebuild HTML report
python -m rea_image.cli report "./rea_output"
```

---

## Ethics and Safety
- Purpose: Learn structure, style, and technique to recreate imagery with assets you have the right to use.
- Do not use this tool to create deceptive replicas of existing intellectual property, trademarks, or personal likenesses.
- AI detection is probabilistic evidence, never absolute proof. Always state confidence honestly and explain what evidence would change the verdict.
- Do not attempt to identify real individuals from faces.

