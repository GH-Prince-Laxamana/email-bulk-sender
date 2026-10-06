from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    """Project-root/data by default; override with BULKMAILER_DATA_DIR."""
    override = os.environ.get("BULKMAILER_DATA_DIR")
    path = Path(override) if override else Path(__file__).resolve().parents[2] / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    return data_dir() / "app.db"
