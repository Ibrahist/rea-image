# Image Decomposition Pipeline

`rea-image` breaks down reference images into spatial, semantic, and craft layers:

```
[Target Image]
      │
      ▼
┌──────────────┐
│ Stage 1:     │ ──> Ingest: Orientation normalize, dHash/pHash, SHA-256
│ Ingest       │
└──────────────┘
      │
      ▼
┌──────────────┐
│ Stage 2:     │ ──> Classical contour & color segmentation + OCR merger
│ Segmentation │     Exports masks and crops to layers/
└──────────────┘
      │
      ▼
┌──────────────┐
│ Stage 3:     │ ──> Provenance, Forensics, Craft (Optics, Lighting, Palette)
│ Evidence     │
└──────────────┘
      │
      ▼
┌──────────────┐
│ Stage 4:     │ ──> Weighted Evidence Fusion (Hard > Forensics > Visual)
│ Judgment     │     Conflict detection -> routes to needs_review
└──────────────┘
      │
      ▼
┌──────────────┐
│ Stage 5 & 6: │ ──> Reverse prompts, Shoot plans, SVG/HTML/Blender scaffolds
│ Recreate     │     Cheapest-viable-path routing & batching
└──────────────┘
      │
      ▼
┌──────────────┐
│ Stage 7:     │ ──> verdict.txt, report.json, report.html, layers/, recreate/
│ Reporting    │
└──────────────┘
```

---

## 1. Semantic Region Segmentation
The image is partitioned into non-overlapping spatial components:
- `background`: Ambient backdrop or border-reaching elements.
- `main_subject`: Highest-contrast or central focal component.
- `foreground_object`: Secondary subjects, props, or geometric entities.
- `text_block`: OCR-detected typographic lines or badges.
- `ui_element`: Rectangular cards, buttons, or navigation chrome.

Each region produces:
- `id`: Unique identifier (e.g., `region_0`)
- `bbox`: Bounding box `[x, y, width, height]`
- `mask`: Binary 8-bit mask in `layers/<id>_mask.png`
- `crop`: Cropped RGB patch in `layers/<id>_crop.png`
- `area_pct`: Percentage contribution to the total canvas.

---

## 2. Craft Deconstruction
- **Camera Optics**: Evaluates depth of field (shallow f/1.4 - f/2.8 vs. deep f/8 - f/16), estimated focal length (wide 24mm vs. normal 50mm vs. telephoto 85mm+), vignetting, and chromatic aberration.
- **Lighting Rigs**: Classifies illumination into one of 12 standard photography setups (Rembrandt, Butterfly, Split, Loop, Softbox, Window light, Ring light, Backlit, Golden hour, Hard direct flash, Neon, Overcast) with detailed gear lists.
- **Color Grading**: Extracts 5-6 dominant palette swatches with semantic roles (`background`, `subject`, `accent`, `text`), dynamic range, and split-toning temperature.
- **Typography**: Identifies font category candidates (Inter, Futura, Times, Impact), weight, size hierarchy, and layout alignment.

