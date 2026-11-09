# Reference: Evidence Detectors and Scoring

This document describes all detectors used in the rea-image pipeline, their categories, signal weights, and physical interpretations.

---

## 1. Category Hierarchy & Weighting Multipliers

Evidence items are evaluated through a tiered weighting system where hard cryptographic and embedded metadata beats forensic measurements, which in turn beat visual heuristics:

| Category | Multiplier | Detectors Included |
|---|:---:|---|
| **Hard Provenance** | `3.0x` | `c2pa_assertion`, `ai_generator_metadata` (A1111/ComfyUI/Invoke chunks), `camera_exif`, `iptc_digital_source_type`, `rendering_software` |
| **Forensic Signals** | `1.8x` | `spectral_peaks_upscaler`, `flat_color_runs`, `jpeg_grid_misalignment`, `noise_inconsistency_composite`, `sensor_poisson_noise`, `synthetic_noise_uncorrelated`, `ela_regional_discrepancy` |
| **Visual / Stylistic** | `1.0x` | `ai_style_plastic_sheen`, `3d_shader_characteristics`, `color_profile_quirk`, `camera_exif_missing` |

---

## 2. Detector Details

### A. Provenance Detectors
- **`c2pa_assertion`**: Scans JPEG/PNG JUMBF manifests. If signed with `c2pa.ai_generative`, confidence is near-total (0.98). If signed by hardware camera capture, verifies camera authenticity.
- **`ai_generator_metadata`**: Parses PNG text chunks (`parameters`, `prompt`, `workflow`, `Comment`) for Stable Diffusion, ComfyUI, Midjourney, and NovelAI. Extracts exact prompts, seed, steps, sampler, and models.
- **`camera_exif`**: Inspects hardware make/model, focal length, aperture, shutter speed, ISO, and GPS tags.
- **`export_software_signature`**: Detects Adobe Photoshop, Lightroom, Canva, Figma, or OS Screen Capture fingerprints.

### B. Forensic Detectors
- **`sensor_poisson_noise` vs. `synthetic_noise_uncorrelated`**: Tests correlation between residual noise variance and signal luminance. Physical sensors exhibit Poisson-Gaussian variance ($Var(I) \propto I$), whereas synthetic diffusion models produce decoupled noise.
- **`noise_inconsistency_composite`**: Compares noise standard deviation across 4 image quadrants. Ratios exceeding 3.0x indicate image splicing or multi-source compositing.
- **`ela_regional_discrepancy`**: Error Level Analysis by recompressing at JPEG 90. High regional error variance flags composite layers with different compression histories.
- **`jpeg_grid_misalignment`**: Checks 8x8 DCT grid periodic phase across boundaries to catch cropped or shifted pasted elements.
- **`spectral_peaks_upscaler`**: Computes 2D FFT power spectrum. Convolutional generator upscalers and checkerboard latent decoders produce discrete harmonic spikes.
- **`flat_color_runs`**: Quantifies consecutive identical horizontal pixels. Vector graphic design and digital UI contain >35% flat pixels, whereas photos contain <1%.

