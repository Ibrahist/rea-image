"""Ingest package for image loading, validation, orientation normalization, and hashing."""

from rea_image.ingest.loader import IngestError, AnimatedImageError, IngestResult, load_image
from rea_image.ingest.hashing import compute_sha256, compute_dhash, compute_phash
from rea_image.ingest.metadata_extractor import extract_metadata, calculate_aspect_ratio_str

__all__ = [
    "IngestError",
    "AnimatedImageError",
    "IngestResult",
    "load_image",
    "compute_sha256",
    "compute_dhash",
    "compute_phash",
    "extract_metadata",
    "calculate_aspect_ratio_str",
]

