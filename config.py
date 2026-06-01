"""Runtime config from environment."""

from __future__ import annotations

import os
from pathlib import Path


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default).strip()


# Pi control (SSH) — use NetBird overlay IPs on the droplet.
PI_IPS: dict[str, str] = {
    "pi4-2": _env("PI4_2_HOST", "100.103.113.117"),
    "pi4-3": _env("PI4_3_HOST", "100.103.175.87"),
}

# Frame storage on edge-1 (HTTP over NetBird only).
STORAGE_BASE_URL: str = _env("STORAGE_BASE_URL", "http://100.103.209.30:8080")

# Path under STORAGE_BASE_URL for each camera latest frame.
PI_LATEST_PATHS: dict[str, str] = {
    "pi4-2": _env("PI4_2_LATEST_PATH", "latest/pi4-2.jpg"),
    "pi4-3": _env("PI4_3_LATEST_PATH", "latest/pi4-3.jpg"),
}

# If true, pull images from edge-1 HTTP. If false, SSH/scp directly from Pis (legacy).
USE_EDGE_STORAGE: bool = _env("USE_EDGE_STORAGE", "true").lower() in ("1", "true", "yes")

PUBLIC_BASE_URL: str = _env("PUBLIC_BASE_URL", "https://gizzagawk.com")

# Optional HTTP Basic Auth (set DASHBOARD_PASSWORD on the droplet).
DASHBOARD_USERNAME: str = _env("DASHBOARD_USERNAME", "david")
DASHBOARD_PASSWORD: str = _env("DASHBOARD_PASSWORD", "")

# Dataset staging on the dashboard host and destination on edge-1.
DATASET_LOCAL_DIR: Path = Path(
    _env(
        "DATASET_LOCAL_DIR",
        str(Path(__file__).resolve().parent / "data" / "datasets"),
    )
)
STORAGE_SSH_HOST: str = _env("STORAGE_SSH_HOST", "100.103.209.30")
STORAGE_SSH_USER: str = _env("STORAGE_SSH_USER", "david")
STORAGE_LAN_HOST: str = _env("STORAGE_LAN_HOST", "192.168.3.11")
STORAGE_DATASETS_DIR: str = _env("STORAGE_DATASETS_DIR", "/data/frames/datasets")
RELAY_PI: str = _env("RELAY_PI", "pi4-2")
