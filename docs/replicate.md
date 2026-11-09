# Image Replication Blueprint & Routing

`rea-image` doesn't just analyze images; it outputs concrete starter blueprints to recreate them through the cheapest viable path.

---

## 1. The Cheapest Viable Path Routing

For every identified region, the replication planner compares four production routes:

| Route | Recommended For | Trade-Off Rationale | Starter File in `recreate/` |
|---|---|---|---|
| **Design** | Typography, logos, UI cards, flat graphics | Zero variable cost, pixel-perfect text control, vector scalability. | `scaffold.svg` or `scaffold.html` |
| **Generate** | Photographic subjects, organic textures, backgrounds | Low cost ($0.02 - $0.05), instant generation, non-deterministic text. | `prompt.txt` |
| **Shoot** | Real human portraits, specific physical products | Optical fidelity and tactile realism; requires camera gear and studio setup. | `shoot_plan.md` |
| **Render** | Hard-surface 3D models, architectural designs | Infinite lighting/angle control, high initial modeling investment. | `starter_scene.py` |

---

## 2. Batching Strategy
- **Co-Generation**: Background and primary visual subjects are batched into a single generation prompt so the diffusion model renders cohesive environment reflections, contact shadows, and depth blur.
- **Separation**: Typographic text, brand marks, and user interface controls are explicitly isolated into vector/design layers. Raster generation models frequently produce spelling artifacts, distorted glyphs, and un-editable text.

---

## 3. Layered Reverse Prompts
Every generation blueprint in `recreate/prompt.txt` includes:
- **Faithful Variant**: Complete decomposition including subject, environment, lighting setup, lens focal length, aperture, color grading, and quality tokens.
- **Simplified Variant**: Minimal essential subject and atmospheric terms.
- **Style Transfer Variant**: Abstracted placeholder `[SUBJECT]` preserving only the reverse-engineered lighting, palette, and camera optics.
- **Negative Prompt**: Targets common diffusion artifacts (extra digits, anatomy flaws, plastic skin, chromatic distortion).

