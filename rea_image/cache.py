"""Disk caching for expensive pipeline steps by image SHA-256 hash and source-fingerprinted step names."""

import json
import logging
import os
from pathlib import Path
import threading
from typing import Any, Optional
from rea_image.config import settings

logger = logging.getLogger(__name__)


class PipelineCache:
    """Stores and retrieves precomputed intermediate results keyed by image SHA-256."""

    def __init__(self, cache_dir: Optional[Path] = None, enabled: Optional[bool] = None):
        self.enabled = settings.cache_enabled if enabled is None else enabled
        self.cache_dir = cache_dir or settings.cache_dir
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, image_sha256: str, step_name: str) -> Path:
        # Create 2-level directory tree from sha256 prefix for filesystem scalability
        prefix = image_sha256[:2]
        target_dir = self.cache_dir / prefix / image_sha256[2:4]
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / f"{image_sha256}_{step_name}.json"

    def get(self, image_sha256: str, step_name: str) -> Optional[Any]:
        """Retrieve cached result if present."""
        if not self.enabled or not image_sha256:
            return None
        try:
            path = self._get_path(image_sha256, step_name)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.debug("Failed to read cache entry %s_%s: %s", image_sha256, step_name, e)
        return None

    def set(self, image_sha256: str, step_name: str, value: Any) -> None:
        """Store result in cache atomically via a temporary file in the same directory."""
        if not self.enabled or not image_sha256:
            return
        temp_path = None
        try:
            path = self._get_path(image_sha256, step_name)
            temp_path = path.with_suffix(f".tmp.{os.getpid()}.{threading.get_ident()}")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(value, f, ensure_ascii=False)
            os.replace(temp_path, path)
        except Exception as e:
            logger.debug("Failed to write cache entry %s_%s: %s", image_sha256, step_name, e)
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    def clear(self) -> None:
        """Wipe entire cache directory."""
        if self.cache_dir.exists():
            import shutil
            shutil.rmtree(self.cache_dir, ignore_errors=True)
            self.cache_dir.mkdir(parents=True, exist_ok=True)


default_cache = PipelineCache()
