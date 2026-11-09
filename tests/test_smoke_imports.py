"""Smoke tests verifying that all modules and subpackages can be imported cleanly."""

import importlib


def test_smoke_imports():
    """Ensure cli, orchestrator, and all subpackages import without error."""
    modules_to_import = [
        "rea_image",
        "rea_image.cli",
        "rea_image.report.orchestrator",
        "rea_image.ingest",
        "rea_image.segment",
        "rea_image.evidence",
        "rea_image.judge",
        "rea_image.reverse",
        "rea_image.replicate",
        "rea_image.capabilities",
        "rea_image.report",
        "rea_image.cache",
        "rea_image.schemas",
        "rea_image.config",
    ]

    for mod in modules_to_import:
        imported = importlib.import_module(mod)
        assert imported is not None, f"Failed to import {mod}"
