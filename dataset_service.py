"""Record multi-camera datasets and upload combined manifests to edge-1."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from config import (
    DATASET_LOCAL_DIR,
    PI_IPS,
    RELAY_PI,
    STORAGE_DATASETS_DIR,
    STORAGE_LAN_HOST,
    STORAGE_SSH_HOST,
    STORAGE_SSH_USER,
)
from pi_remote import (
    list_remote_frame_paths_in_window,
    parse_capture_time_from_name,
    scp_from_pi,
)

STATE_FILE = DATASET_LOCAL_DIR / "dataset_state.json"


@dataclass
class DatasetState:
    status: str = "idle"
    name: str = ""
    details: str = ""
    dataset_id: str = ""
    started_at: str | None = None
    stopped_at: str | None = None
    frame_count: int | None = None
    storage_path: str | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_state() -> DatasetState:
    if not STATE_FILE.is_file():
        return DatasetState()
    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return DatasetState(**data)


def save_state(state: DatasetState) -> None:
    DATASET_LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")


def slugify_name(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return slug[:48] if slug else "dataset"


def start_dataset(name: str, details: str) -> DatasetState:
    state = load_state()
    if state.status == "recording":
        state.message = "A dataset is already recording. Stop it first."
        return state
    if not name.strip():
        state.message = "Dataset name is required."
        return state
    now = datetime.utcnow()
    dataset_id = f"{slugify_name(name)}_{now.strftime('%Y%m%d_%H%M%S')}"
    new_state = DatasetState(
        status="recording",
        name=name.strip(),
        details=details.strip(),
        dataset_id=dataset_id,
        started_at=now.isoformat(timespec="seconds") + "Z",
        message=f"Recording dataset “{name.strip()}” from all cameras.",
    )
    save_state(new_state)
    return new_state


def stop_dataset() -> DatasetState:
    state = load_state()
    if state.status != "recording":
        state.message = "No dataset is currently recording."
        return state
    state.status = "stopped"
    state.stopped_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    state.message = "Recording stopped. Review and send to storage when ready."
    save_state(state)
    return state


def reset_dataset() -> DatasetState:
    state = DatasetState(message="Ready for a new dataset.")
    save_state(state)
    return state


@dataclass(frozen=True)
class FrameEntry:
    timestamp: datetime
    camera_id: str
    remote_path: str
    local_filename: str

    def to_manifest_dict(self) -> dict[str, str]:
        return {
            "timestamp": self.timestamp.strftime("%Y-%m-%dT%H:%M:%S"),
            "camera_id": self.camera_id,
            "filename": f"images/{self.local_filename}",
            "source_remote": self.remote_path,
        }


def collect_frames_in_window(
    started_at: datetime,
    stopped_at: datetime,
) -> list[FrameEntry]:
    entries: list[FrameEntry] = []
    for camera_id, ip in PI_IPS.items():
        for remote_path in list_remote_frame_paths_in_window(
            camera_id, ip, started_at, stopped_at
        ):
            capture_time = parse_capture_time_from_name(Path(remote_path))
            if capture_time is None:
                continue
            if capture_time < started_at or capture_time > stopped_at:
                continue
            local_filename = (
                f"{camera_id}_{capture_time.strftime('%Y%m%d_%H%M%S')}.jpg"
            )
            entries.append(
                FrameEntry(
                    timestamp=capture_time,
                    camera_id=camera_id,
                    remote_path=remote_path,
                    local_filename=local_filename,
                )
            )
    entries.sort(key=lambda entry: (entry.timestamp, entry.camera_id))
    return entries


def build_dataset_package(state: DatasetState) -> tuple[Path, list[FrameEntry]]:
    if not state.started_at or not state.stopped_at:
        raise ValueError("Dataset window is incomplete.")
    started_at = datetime.fromisoformat(state.started_at.replace("Z", ""))
    stopped_at = datetime.fromisoformat(state.stopped_at.replace("Z", ""))
    entries = collect_frames_in_window(started_at, stopped_at)
    dataset_dir = DATASET_LOCAL_DIR / state.dataset_id
    images_dir = dataset_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        ip = PI_IPS[entry.camera_id]
        local_path = images_dir / entry.local_filename
        if not scp_from_pi(ip, entry.remote_path, local_path):
            raise RuntimeError(
                f"Failed to copy {entry.remote_path} from {entry.camera_id}"
            )
    manifest: dict[str, Any] = {
        "dataset_id": state.dataset_id,
        "name": state.name,
        "details": state.details,
        "started_at": state.started_at,
        "stopped_at": state.stopped_at,
        "frame_count": len(entries),
        "cameras": sorted(PI_IPS.keys()),
        "frames": [entry.to_manifest_dict() for entry in entries],
    }
    manifest_path = dataset_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return dataset_dir, entries


def upload_dataset_to_storage(dataset_dir: Path, dataset_id: str) -> tuple[bool, str]:
    return _upload_dataset_via_pi_relay(dataset_dir, dataset_id)


def _upload_dataset_direct(dataset_dir: Path, dataset_id: str) -> tuple[bool, str]:
    remote_path = f"{STORAGE_SSH_USER}@{STORAGE_SSH_HOST}:{STORAGE_DATASETS_DIR}/{dataset_id}/"
    mkdir_cmd = f"mkdir -p {STORAGE_DATASETS_DIR}/{dataset_id}"
    mkdir_result = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            f"{STORAGE_SSH_USER}@{STORAGE_SSH_HOST}",
            mkdir_cmd,
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if mkdir_result.returncode != 0:
        detail = (mkdir_result.stderr or mkdir_result.stdout or "SSH failed").strip()
        return False, detail[:300]
    rsync_result = subprocess.run(
        [
            "rsync",
            "-avz",
            "-e",
            "ssh -o BatchMode=yes -o ConnectTimeout=10",
            f"{dataset_dir}/",
            remote_path,
        ],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if rsync_result.returncode != 0:
        detail = (rsync_result.stderr or rsync_result.stdout or "rsync failed").strip()
        return False, detail[:300]
    return True, f"{STORAGE_DATASETS_DIR}/{dataset_id}/"


def _upload_dataset_via_pi_relay(dataset_dir: Path, dataset_id: str) -> tuple[bool, str]:
    relay_ip = PI_IPS.get(RELAY_PI)
    if not relay_ip:
        return False, f"Relay Pi {RELAY_PI} is not configured."
    remote_staging = f"/tmp/dataset_upload/{dataset_id}"
    mkdir_result = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=15",
            f"root@{relay_ip}",
            f"mkdir -p {remote_staging}",
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if mkdir_result.returncode != 0:
        detail = (mkdir_result.stderr or mkdir_result.stdout or "mkdir failed").strip()
        return False, f"Relay staging mkdir failed: {detail[:250]}"
    staging_result = subprocess.run(
        [
            "rsync",
            "-avz",
            "-e",
            "ssh -o BatchMode=yes -o ConnectTimeout=15",
            f"{dataset_dir}/",
            f"root@{relay_ip}:{remote_staging}/",
        ],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if staging_result.returncode != 0:
        detail = (staging_result.stderr or staging_result.stdout or "staging failed").strip()
        return False, f"Relay staging failed: {detail[:250]}"
    push_cmd = (
        f"ssh-keyscan -H {STORAGE_LAN_HOST} >> ~/.ssh/known_hosts 2>/dev/null; "
        f"mkdir -p {STORAGE_DATASETS_DIR}/{dataset_id} && "
        f"rsync -avz {remote_staging}/ "
        f"{STORAGE_SSH_USER}@{STORAGE_LAN_HOST}:{STORAGE_DATASETS_DIR}/{dataset_id}/ && "
        f"rm -rf {remote_staging}"
    )
    push_result = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=15",
            f"root@{relay_ip}",
            push_cmd,
        ],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if push_result.returncode != 0:
        detail = (push_result.stderr or push_result.stdout or "relay push failed").strip()
        return False, f"Relay push failed: {detail[:250]}"
    return True, f"{STORAGE_DATASETS_DIR}/{dataset_id}/ (via {RELAY_PI} relay)"


def send_dataset_to_storage() -> DatasetState:
    state = load_state()
    if state.status != "stopped":
        state.message = "Stop the dataset before sending to storage."
        return state
    try:
        dataset_dir, entries = build_dataset_package(state)
        if not entries:
            state.message = (
                "No frames found in the recording window. "
                "Keep cameras ON while recording, then try Send again."
            )
            save_state(state)
            return state
        ok, detail = upload_dataset_to_storage(dataset_dir, state.dataset_id)
        if not ok:
            state.frame_count = len(entries)
            state.message = f"Upload failed: {detail.splitlines()[0][:200]}"
            save_state(state)
            return state
        state.status = "sent"
        state.frame_count = len(entries)
        state.storage_path = detail
        state.message = (
            f"Sent {len(entries)} frames to edge-1. "
            f"Manifest combines all cameras sorted by timestamp."
        )
        save_state(state)
        return state
    except Exception as err:
        state.message = f"Dataset build failed: {err}"
        save_state(state)
        return state
