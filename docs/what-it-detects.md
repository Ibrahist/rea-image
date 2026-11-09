# What rea-image Detects

`rea-image` is designed to deconstruct still images and classify them into one of seven distinct production methods:

1. **Real Photograph** (camera or smartphone capture)
2. **AI-Generated** (text-to-image, image-to-image, inpainted, or diffusion edited)
3. **3D Render** (Blender, Cinema 4D, Unreal Engine, Maya)
4. **Vector or Graphic Design** (posters, banners, infographics, logos)
5. **UI or Screenshot** (web, desktop, mobile applications, documents)
6. **Illustration or Painting** (digital painting or scanned traditional media)
7. **Composite** (mixed media, e.g. photo + AI background + designed typography)

---

## Detection Signals Breakdown

### 1. Hard Provenance & Metadata (Weight: 3.0x)
- **EXIF / XMP / IPTC**: Hardware camera make, model, lens specifications, focal length, aperture, shutter speed, ISO gain, and GPS coordinate presence.
- **C2PA / Content Credentials**: Cryptographic verification of JUMBF manifests, including digital signatures and `c2pa.ai_generative` assertions.
- **AI Generator Traces**: PNG metadata chunks (`parameters`, `prompt`, `workflow`, `Comment`) left by Automatic1111, ComfyUI, Midjourney, NovelAI, and InvokeAI. Extracts positive prompts, negative prompts, seeds, steps, samplers, and model names.
- **Export Traces**: Identifies software fingerprints (Photoshop, Lightroom, Canva, Figma, Blender, Apple Display Capture) and matches JPEG quantization tables against encoder profiles.

### 2. Digital Forensics (Weight: 1.8x)
- **Residual Noise Analysis**: Poisson-Gaussian shot noise correlation ($Var(I) \propto I$) for real camera sensors versus uncorrelated or hyper-smooth synthetic noise profiles.
- **Error Level Analysis (ELA)**: Recompression delta measurements at JPEG 90. Identifies regional variance anomalies typical of pasted or spliced layers.
- **JPEG DCT Blocking Alignment**: Inspects 8x8 DCT grid phase continuity to detect translated, rotated, or cropped composite elements.
- **2D FFT Frequency Analysis**: Detects periodic harmonic spikes caused by neural generator upscalers and transposed convolutions, alongside power-law radial frequency falloff ($1/f^\alpha$).
- **Flat Region Run-Length**: Measures consecutive identical RGB runs and unique color entropy to distinguish lossless vector/UI graphics from textured natural scenes.

### 3. Visual & Stylistic Tells (Weight: 1.0x)
- **AI Style Tells**: Identifies low midtone texture variation coupled with specular spot highlights ("plastic sheen").
- **3D Render Shaders**: Evaluates mathematical geometric edge sharpness and PBR material rolloff typical of Cycles/Eevee.
- **Degradation Penalties**: Quantifies heavy compression artifacts and resolution limits, automatically attenuating forensic confidence on degraded files.

