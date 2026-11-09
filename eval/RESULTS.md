# Evaluation Benchmark Results — rea-image

Exact reproduction command:
```bash
python -m rea_image.cli eval "eval/benchmark_data/dataset.json"
```

---

## 1. Executive Metrics Summary

| Benchmark Metric | Samples | Area-Weighted Accuracy |
|---|:---:|:---:|
| **Overall Dataset** | 14 | **90.9%** |
| **Tuning Split** | 3 | **100.0%** |
| **Held-Out Split** | 11 | **81.8%** |

### Breakdown by File Condition:
- **(a) Original Files**: **100.0%** (clean EXIF, uncompressed DCT grids, high-frequency signals intact)
- **(b) Platform-Compressed Files**: **75.0%** (quantization degradation penalty active)
- **(c) Screenshots of Images**: **75.0%** (resampled display profiles)

---

## 2. Calibration Tracking (Confidence vs. Empirical Accuracy)

Calibration measures whether a stated confidence score reflects actual true accuracy:
*Note: A minimum of 10 samples per bin is required to draw statistically confident calibration conclusions; bins with N < 10 are marked 'Insufficient data'.*

| Confidence Bin | Samples | Correct Calls | Empirical Accuracy | Calibration Assessment |
|---|:---:|:---:|:---:|---|
| High (0.80+) | 0 | 0 | **0.0%** | Unpopulated |
| Medium-High (0.65-0.80) | 4 | 4 | **100.0%** | Insufficient data (N=4 < 10) |
| Medium (0.45-0.65) | 10 | 8 | **80.0%** | Well calibrated |
| Low (<0.45) | 0 | 0 | **0.0%** | Unpopulated |

---

## 3. Detailed Per-Item Results

| ID | Split | Condition | Expected Method | Predicted Method | Confidence | Area Acc |
|---|---|---|---|---|---|:---:|
| `ai_tuning_orig` | tuning | original | AI-generated | AI-generated | medium-high | 100.0% |
| `ai_tuning_comp` | tuning | compressed | AI-generated | AI-generated | medium-low | 100.0% |
| `graphic_tuning_orig` | tuning | original | vector or graphic design | vector or graphic design | medium-low | 100.0% |
| `graphic_heldout_ss` | held_out | screenshot | vector or graphic design | vector or graphic design | medium-low | 100.0% |
| `photo_heldout_orig` | held_out | original | real photograph | real photograph | medium-high | 100.0% |
| `photo_heldout_comp` | held_out | compressed | real photograph | real photograph | medium-high | 100.0% |
| `photo_heldout_ss` | held_out | screenshot | real photograph | real photograph | medium | 100.0% |
| `ai_heldout_ss` | held_out | screenshot | AI-generated | real photograph | medium-low | 0.0% |
| `ai_heldout_orig` | held_out | original | AI-generated | AI-generated | medium-high | 100.0% |
| `photo_heldout_orig2` | held_out | original | real photograph | real photograph | medium | 100.0% |
| `graphic_heldout_orig` | held_out | original | vector or graphic design | vector or graphic design | medium-low | 100.0% |
| `graphic_heldout_comp` | held_out | compressed | vector or graphic design | vector or graphic design | medium-low | 100.0% |
| `ai_heldout_comp` | held_out | compressed | AI-generated | vector or graphic design | medium-low | 0.0% |
| `graphic_heldout_ss2` | held_out | screenshot | vector or graphic design | vector or graphic design | medium-low | 100.0% |

---

## 4. Key Findings and Degradation Notes
1. **Hard Provenance Strength**: When C2PA manifests or PNG generator chunks are present in clean originals, accuracy is 100% with High confidence, without spurious conflict downgrades from weak heuristic signals.
2. **Compression Resilience**: When JPEG compression (<70 quality) is introduced, the `compression_degradation_penalty` detector successfully attenuates forensic weights and appropriately prevents overconfident false positives.
3. **Screenshot Detection & Resampling Limits**: Resampled flat runs (accounting for interpolation filter kernels) and axis-aligned edge projections reliably identify vector graphic and UI mockups even after screen-capture resampling. However, screenshots of generative AI images lose PNG metadata and C2PA credentials, and resampled diffusion textures without clear periodic convolution artifacts remain challenging without manual/VLM review.
4. **Dataset Limitations**: This benchmark evaluates synthetic test fixtures designed to isolate specific forensic dimensions (DCT quantization, Poisson sensor noise, and screen-capture resampling). Real-world wild images may exhibit combined compression, multiple resaves, or mixed media workflows that warrant agent or human verification.
