# Evaluation Harness for rea-image

This directory contains the evaluation dataset schema, test runner, and benchmark results measuring classification accuracy, area-weighted segmentation precision, and confidence calibration.

---

## 1. Running the Benchmark

To run the evaluation harness:
```bash
python -m rea_image.cli eval eval/benchmark_data/dataset.json
```

---

## 2. Benchmark Design

The evaluation dataset evaluates images across:
- **Tuning Split**: Used for parameter calibration and threshold optimization.
- **Held-Out Split**: Held-out test set to ensure generalizability without data leakage.

Images are evaluated under three distinct conditions:
1. **(a) Clean Originals**: Unmodified original files with intact EXIF, PNG chunks, and raw frequency spectra.
2. **(b) Platform-Compressed**: Files re-compressed using JPEG (qualities 50-85) to simulate messaging apps and web uploads.
3. **(c) Screenshots**: Scaled and resampled images simulating operating system display captures.

---

## 3. Results and Metrics
Detailed metrics and calibration assessments are automatically compiled in [`RESULTS.md`](RESULTS.md).

