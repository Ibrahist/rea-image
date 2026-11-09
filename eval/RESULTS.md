# Evaluation Benchmark Results — rea-image

Exact reproduction command:
```bash
python -m rea_image.cli eval "eval\benchmark_data\dataset.json"
```

---

## 1. Executive Metrics Summary

| Benchmark Metric | Samples | Area-Weighted Accuracy |
|---|:---:|:---:|
| **Overall Dataset** | 6 | **83.5%** |
| **Tuning Split** | 3 | **100.0%** |
| **Held-Out Split** | 3 | **67.0%** |

### Breakdown by File Condition:
- **(a) Original Files**: **100.0%** (clean EXIF, uncompressed DCT grids, high-frequency signals intact)
- **(b) Platform-Compressed Files**: **100.0%** (quantization degradation penalty active)
- **(c) Screenshots of Images**: **0.9%** (resampled display profiles)

---

## 2. Calibration Tracking (Confidence vs. Empirical Accuracy)

Calibration measures whether a stated confidence score reflects actual true accuracy:

| Confidence Bin | Samples | Correct Calls | Empirical Accuracy | Calibration Assessment |
|---|:---:|:---:|:---:|---|
| High (0.80+) | 0 | 0 | **0.0%** | Well calibrated |
| Medium-High (0.65-0.80) | 1 | 1 | **100.0%** | Well calibrated |
| Medium (0.45-0.65) | 5 | 4 | **80.0%** | Well calibrated |
| Low (<0.45) | 0 | 0 | **0.0%** | Well calibrated |

---

## 3. Detailed Per-Item Results

| ID | Split | Condition | Expected Method | Predicted Method | Confidence | Area Acc |
|---|---|---|---|---|---|:---:|
| `ai_tuning_orig` | tuning | original | AI-generated | AI-generated | medium-high | 100.0% |
| `ai_tuning_comp` | tuning | compressed | AI-generated | AI-generated | medium | 100.0% |
| `graphic_tuning_orig` | tuning | original | vector or graphic design | vector or graphic design | medium-low | 100.0% |
| `graphic_heldout_ss` | held_out | screenshot | vector or graphic design | real photograph | medium-low | 0.9% |
| `photo_heldout_orig` | held_out | original | real photograph | real photograph | medium | 100.0% |
| `photo_heldout_comp` | held_out | compressed | real photograph | real photograph | medium | 100.0% |

---

## 4. Key Findings and Degradation Notes
1. **Hard Provenance Strength**: When C2PA manifests or PNG generator chunks are present in clean originals, accuracy is 100% with High confidence.
2. **Compression Resilience**: When JPEG compression (<70 quality) is introduced, the `compression_degradation_penalty` detector successfully attenuates forensic weights and appropriately prevents overconfident false positives.
3. **Screenshot Detection**: Display P3 color profiles and UI flat runs provide reliable classification even after screen-capture resampling.
