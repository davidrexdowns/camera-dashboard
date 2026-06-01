"""SSH/SCP helpers for Raspberry Pi edge-client frame paths."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

PI_REMOTE_GLOBS: dict[str, list[str]] = {
    "pi4-2": ["*pi4-2*.jpg", "*edge-pi2*.jpg"],
    "pi4-3": ["*pi4-3*.jpg", "*edge-pi1*.jpg"],
}

CAPTURE_TIME_PATTERN = re.compile(r"_(\d{8})_(\d{6})\.jpg$", re.IGNORECASE)
REMOTE_DATA_ROOT = "/root/edge-client/data"
REMOTE_SESSION_GLOB = f"{REMOTE_DATA_ROOT}/session_*"
REMOTE_RAW_DIR = f"{REMOTE_DATA_ROOT}/raw"


def parse_capture_time_from_name(path: Path) -> datetime | None:
    match = CAPTURE_TIME_PATTERN.search(path.name)
    if not match:
        return None
    date_part, time_part = match.group(1), match.group(2)
    try:
        return datetime.strptime(f"{date_part}{time_part}", "%Y%m%d%H%M%S")
    except ValueError:
        return None


def build_remote_ls_command(pi: str) -> str:
    patterns = PI_REMOTE_GLOBS.get(pi, [f"*{pi}*.jpg"])
    glob_paths: list[str] = []
    for pattern in patterns:
        glob_paths.append(f"{REMOTE_SESSION_GLOB}/{pattern}")
        glob_paths.append(f"{REMOTE_RAW_DIR}/{pattern}")
    all_globs = " ".join(glob_paths)
    return f"ls -1t {all_globs} 2>/dev/null | head -1"


def build_remote_list_all_command(pi: str) -> str:
    patterns = PI_REMOTE_GLOBS.get(pi, [f"*{pi}*.jpg"])
    name_tests: list[str] = []
    for pattern in patterns:
        name_tests.append(f"-name {pattern}")
    name_clause = " -o ".join(name_tests)
    return (
        f"find {REMOTE_DATA_ROOT} "
        f"\\( -path '{REMOTE_DATA_ROOT}/session_*/*' "
        f"-o -path '{REMOTE_DATA_ROOT}/raw/*' \\) "
        f"-type f \\( {name_clause} \\) 2>/dev/null"
    )


def run_pi_ssh_command(ip: str, remote_command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=8",
            f"root@{ip}",
            remote_command,
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def scp_from_pi(ip: str, remote_path: str, local_path: Path) -> bool:
    result = subprocess.run(
        [
            "scp",
            "-q",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=8",
            f"root@{ip}:{remote_path}",
            str(local_path),
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    return result.returncode == 0 and local_path.is_file()


def fetch_newest_remote_path(pi: str, ip: str) -> str | None:
    result = run_pi_ssh_command(ip, build_remote_ls_command(pi))
    if result.returncode != 0:
        return None
    line = result.stdout.strip()
    return line if line else None


def build_remote_list_window_command(
    pi: str,
    started_at: datetime,
    stopped_at: datetime,
) -> str:
    patterns = PI_REMOTE_GLOBS.get(pi, [f"*{pi}*.jpg"])
    name_tests: list[str] = []
    for pattern in patterns:
        name_tests.append(f"-name {pattern}")
    name_clause = " -o ".join(name_tests)
    search_from = (started_at - timedelta(seconds=60)).strftime("%Y-%m-%d %H:%M:%S")
    search_to = (stopped_at + timedelta(seconds=60)).strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"find {REMOTE_DATA_ROOT}/session_* {REMOTE_RAW_DIR} "
        f"-mindepth 1 -maxdepth 2 -type f "
        f"\\( {name_clause} \\) "
        f"-newermt '{search_from}' ! -newermt '{search_to}' 2>/dev/null"
    )


def list_remote_frame_paths_in_window(
    pi: str,
    ip: str,
    started_at: datetime,
    stopped_at: datetime,
) -> list[str]:
    result = run_pi_ssh_command(
        ip,
        build_remote_list_window_command(pi, started_at, stopped_at),
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if lines:
        return lines
    return list_remote_frame_paths(pi, ip)


def list_remote_frame_paths(pi: str, ip: str) -> list[str]:
    result = run_pi_ssh_command(ip, build_remote_list_all_command(pi))
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if lines:
        return lines
    if result.returncode != 0:
        return []
    return []


def run_pi_systemctl(ip: str, action: str) -> tuple[bool, str]:
    result = run_pi_ssh_command(ip, f"systemctl {action} edge-client.service")
    if result.returncode == 0:
        return True, ""
    detail = (result.stderr or result.stdout or "SSH failed").strip()
    return False, detail[:200]
