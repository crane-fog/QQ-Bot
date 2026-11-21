"""Standalone deployment panel; importing this package never initializes the Bot."""

from pathlib import Path


def default_source_root() -> Path:
    return Path(__file__).resolve().parents[2]
