"""Fetch latest frames from edge-1 storage over NetBird HTTP."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from config import PI_LATEST_PATHS, STORAGE_BASE_URL


def fetch_latest_from_storage(
    pi: str,
    static_dir: Path,
) -> tuple[Path | None, datetime | None, str, str]:
    """
    Download latest/{pi}.jpg from edge-1 into static/latest_{pi}.jpg.

    Returns (local_path, capture_time, source_label, error_message).
    """
    rel_path = PI_LATEST_PATHS.get(pi, f"latest/{pi}.jpg")
    base = STORAGE_BASE_URL.rstrip("/")
    url = f"{base}/{rel_path}"
    local_path = static_dir / f"latest_{pi}.jpg"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = response.read()
        if len(data) < 100:
            return None, None, "", "empty or missing image on storage node"
        local_path.write_bytes(data)
        capture_time = _parse_capture_from_url_or_mtime(local_path, rel_path)
        return local_path, capture_time, f"edge-1:{rel_path}", ""
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None, None, "", f"no file yet at {url} (Pi must push to edge-1)"
        return None, None, "", f"storage HTTP {exc.code}: {url}"
    except urllib.error.URLError as exc:
        return None, None, "", f"cannot reach storage at {base} ({exc.reason})"


def _parse_capture_from_url_or_mtime(local_path: Path, rel_path: str) -> datetime | None:
    import re

    match = re.search(r"_(\d{8})_(\d{6})\.jpg", rel_path, re.IGNORECASE)
    if match:
        try:
            return datetime.strptime(f"{match.group(1)}{match.group(2)}", "%Y%m%d%H%M%S")
        except ValueError:
            pass
    return datetime.fromtimestamp(local_path.stat().st_mtime)
