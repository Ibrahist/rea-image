# Reference: Recreation Blueprint Guide

This guide explains how to use the outputs generated in `recreate/` to rebuild or produce derivatives of analyzed images using the cheapest viable path.

---

## 1. Choosing the Cheapest Viable Path

The replication planner evaluates trade-offs across four production routes:

| Route | Cheapest For | Trade-offs | Key Tools |
|---|---|---|---|
| **Design / Code** | Typography, UI, infographics, logos | Zero variable cost, pixel-perfect control, 100% deterministic text | Figma, HTML/CSS, SVG, Penpot |
| **Generate (AI)** | Complex natural scenes, conceptual art, fantasy backgrounds | ~$0.02 - $0.05 per image, 2-minute cycle, non-deterministic text | FLUX.1 [dev], Midjourney, SDXL |
| **Shoot (Photo)** | Real people, authentic product shoots, local physical spaces | Highest optical realism, requires camera gear, location, and post | DSLR/Mirrorless, 50mm f/1.8, Octabox |
| **Render (3D)** | Hard-surface industrial design, isometric rooms, architectural visualization | High initial modeling time, zero camera/travel cost, full lighting control | Blender 4.x (Cycles), Three.js |

---

## 2. Batching Strategy

### Safe to Batch Together:
- **Main Subject + Ambient Background**: Diffusion models naturally render environmental interaction (ground shadows, ambient light bouncing, depth of field blur).

### Must Be Isolated and Composited:
- **Typography & Glyphs**: Raster AI models struggle with consistent font rendering, character tracking, and spelling. Text regions should always be added using `scaffold.svg` or vector design tools.
- **Logos & Badges**: Vector elements pasted on AI backdrops preserve brand geometry and sharp anti-aliasing.

---

## 3. Layered Prompt Architecture

When using `recreate/prompt.txt`, prompts follow a 7-tier decomposition:
1. **Subject**: Core entity and primary action.
2. **Setting**: Spatial location, background props, atmospheric depth.
3. **Medium**: Photography, digital illustration, 3D render.
4. **Camera / Optics**: Focal length class, aperture, perspective compression.
5. **Lighting**: Setup name (e.g. Rembrandt, Loop, Golden hour), light direction, color temperature.
6. **Color Grade**: Dominant palette roles, contrast level, split-toning.
7. **Quality**: Resolution, surface micro-textures, framing.

