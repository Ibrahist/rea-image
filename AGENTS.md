# AGENTS.md — rea-image Agent Integration Guide

Welcome, Agent. This repository contains **rea-image**, an open-source tool and agent skill that reverse-engineers any still image: it deconstructs how the image was made, extracts supporting and contradicting evidence, and produces an actionable recreation plan.

---

## 1. Primary Instruction
Whenever a user asks you to:
- "Reverse-engineer this image"
- "Break down how this picture was created"
- "Detect whether this image is AI or a real photo"
- "Give me the prompt / lighting / recreate plan for this image"

You should **immediately load and follow the skill at `skills/rea-image/SKILL.md`**.

---

## 2. Quick Command Reference

```bash
# Analyze a single image (offline, deterministic-first)
python -m rea_image.cli analyze /path/to/image.png --out ./rea_output

# Analyze with agent review mode (exports crops and questions for you)
python -m rea_image.cli analyze /path/to/image.png --agent-review

# Inspect provenance and metadata only
python -m rea_image.cli provenance /path/to/image.png

# Extract color palette and grading
python -m rea_image.cli palette /path/to/image.png

# Extract or reverse-engineer generation prompt
python -m rea_image.cli prompt /path/to/image.png

# Rebuild interactive HTML report
python -m rea_image.cli report ./rea_output

# Run dry-run recreation simulation
python -m rea_image.cli recreate ./rea_output --dry-run
```

---

## 3. Output Structure
Every analysis run produces the following artifacts in the output directory:
- `verdict.txt`: One-line summary (e.g. `AI-generated 78% + designed text 22%; Midjourney-style; 4:5; confidence medium-high`).
- `report.json`: Full machine-readable schema detailing image metadata, regional breakdowns, evidence items, and recreation plans.
- `report.html`: Self-contained interactive report with region overlay toggles, composition guides, and color swatches.
- `layers/`: Binary masks and cropped image patches for each identified region.
- `recreate/`: Actionable starter files (`prompt.txt`, `scaffold.svg`, `scaffold.html`, `shoot_plan.md`, `starter_scene.py`).

---

## 4. Agent Review Mode (`--agent-review`)
When analyzing ambiguous or conflicting images (e.g. camera EXIF present but visual anatomy flaws observed):
1. `report.json` populates `needs_review: [{"region_id", "reason", "question_for_agent"}]`.
2. Inspect the crops in `layers/` using your native vision capabilities.
3. Answer the specific question formulate in `needs_review` to synthesize the final conclusion for the user.

