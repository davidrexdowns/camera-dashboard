from __future__ import annotations

import asyncio
import subprocess
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Form, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from auth import BasicAuthMiddleware, is_auth_enabled
from config import PI_IPS, PUBLIC_BASE_URL, USE_EDGE_STORAGE
from dataset_service import (
    load_state,
    reset_dataset,
    send_dataset_to_storage,
    start_dataset,
    stop_dataset,
)
from dataset_ui import render_dataset_panel
from pi_remote import (
    fetch_newest_remote_path,
    parse_capture_time_from_name,
    run_pi_systemctl,
    scp_from_pi,
)
from storage_client import fetch_latest_from_storage

app = FastAPI(title="gizz a gawk, frame capture for object motion physics models")
app.add_middleware(BasicAuthMiddleware)

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def copy_to_latest_slot(ip: str, remote_path: str, pi: str, static_dir: Path) -> Path | None:
    latest_local = static_dir / f"latest_{pi}.jpg"
    if not scp_from_pi(ip, remote_path, latest_local):
        return None
    return latest_local


def fetch_latest_image(pi: str, ip: str, static_dir: Path) -> tuple[Path | None, datetime | None, str]:
    remote_path = fetch_newest_remote_path(pi, ip)
    if remote_path:
        local_path = copy_to_latest_slot(ip, remote_path, pi, static_dir)
        if local_path:
            source_name = Path(remote_path).name
            capture_time = parse_capture_time_from_name(Path(source_name))
            return local_path, capture_time, source_name
    local_candidates = [
        *static_dir.glob(f"latest_{pi}.jpg"),
        *static_dir.glob(f"*{pi}*.jpg"),
        *static_dir.glob(f"*edge-pi{'2' if pi == 'pi4-2' else '1'}*.jpg"),
    ]
    if not local_candidates:
        return None, None, ""
    best_local = max(local_candidates, key=lambda path: path.stat().st_mtime)
    return (
        best_local,
        parse_capture_time_from_name(best_local),
        best_local.name,
    )


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    public_base_url = PUBLIC_BASE_URL or "https://gizzagawk.com"
    dataset_panel = render_dataset_panel(load_state())
    return HTMLResponse(
        """
<!DOCTYPE html>
<html>
<head>
    <title>gizz a gawk, frame capture for object motion physics models</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400&display=swap" rel="stylesheet">
    <script src="https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js"></script>
    <style>
        body {
            font-family: "IBM Plex Mono", "Courier New", monospace;
            font-weight: 400;
            margin: 20px;
            background: #f4f4f4;
        }
        .page-header {
            max-width: 900px;
            margin-bottom: 24px;
        }
        .header-logo {
            width: 273px;
            height: auto;
            border-radius: 8px;
            display: block;
            margin-bottom: 12px;
        }
        h1 {
            font-weight: 400;
            font-size: 1.35rem;
            line-height: 1.45;
            letter-spacing: -0.01em;
            margin: 0;
            max-width: 28rem;
        }
        .camera, .dataset-panel {
            border: 2px solid #333;
            padding: 20px;
            margin: 15px 0;
            border-radius: 10px;
            background: white;
            max-width: 650px;
        }
        button {
            padding: 12px 24px;
            margin: 8px 5px 8px 0;
            font-size: 16px;
            cursor: pointer;
        }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        .status { margin: 10px 0; font-weight: bold; }
        .latest img { max-width: 100%; margin-top: 10px; border: 2px solid #ddd; border-radius: 8px; }
        .meta { font-size: 13px; color: #555; margin-top: 6px; }
        .overlay-hint { max-width: 650px; margin: 0 0 20px 0; }
        .overlay-hint a { color: #333; }
        .dataset-form { margin-top: 12px; }
        .dataset-label {
            display: block;
            font-size: 13px;
            margin: 10px 0 4px 0;
        }
        .dataset-form input[type="text"],
        .dataset-form textarea {
            width: 100%;
            max-width: 100%;
            box-sizing: border-box;
            font-family: inherit;
            font-size: 14px;
            padding: 8px;
            border: 1px solid #ccc;
            border-radius: 6px;
        }
        .dataset-start { background: #2e7d32; color: white; border: none; border-radius: 6px; }
        .dataset-stop { background: #c62828; color: white; border: none; border-radius: 6px; }
        .dataset-send { background: #1565c0; color: white; border: none; border-radius: 6px; }
        .dataset-new { background: #555; color: white; border: none; border-radius: 6px; }
        .dataset-message { margin: 8px 0; }
        .dataset-status { margin: 8px 0; }
        .htmx-indicator { display: none; margin-left: 8px; font-size: 13px; color: #555; }
        .htmx-request .htmx-indicator { display: inline; }
        .htmx-request.htmx-indicator { display: inline; }
    </style>
</head>
<body>
    <header class="page-header">
        <img class="header-logo" src="/static/gawk_logo.png" alt="Gawk agent">
        <h1>gizz a gawk, frame capture for object motion physics models</h1>
    </header>
    <p class="meta overlay-hint">Site: <a href="__PUBLIC_BASE_URL__">__PUBLIC_BASE_URL__</a> · Latest frame pulled from Pi on each click</p>

    <div id="dataset-panel" class="dataset-panel">
__DATASET_PANEL__
    </div>

    <div class="camera">
        <h2>Pi4-3</h2>
        <button hx-post="/control/pi4-3/on" hx-target="#status-pi43">Turn ON</button>
        <button hx-post="/control/pi4-3/off" hx-target="#status-pi43">Turn OFF</button>
        <button hx-get="/latest/pi4-3" hx-target="#image-pi43"
                hx-vals="js:{_t: Date.now()}">Show Latest Frame</button>
        <div id="status-pi43" class="status">Status: Ready</div>
        <div id="image-pi43" class="latest"></div>
    </div>

    <div class="camera">
        <h2>Pi4-2</h2>
        <button hx-post="/control/pi4-2/on" hx-target="#status-pi42">Turn ON</button>
        <button hx-post="/control/pi4-2/off" hx-target="#status-pi42">Turn OFF</button>
        <button hx-get="/latest/pi4-2" hx-target="#image-pi42"
                hx-vals="js:{_t: Date.now()}">Show Latest Frame</button>
        <div id="status-pi42" class="status">Status: Ready</div>
        <div id="image-pi42" class="latest"></div>
    </div>
</body>
</html>
        """
        .replace("__PUBLIC_BASE_URL__", public_base_url)
        .replace("__DATASET_PANEL__", dataset_panel)
    )


@app.get("/dataset/panel", response_class=HTMLResponse)
async def dataset_panel() -> HTMLResponse:
    return HTMLResponse(render_dataset_panel(load_state()))


@app.post("/dataset/start", response_class=HTMLResponse)
async def dataset_start(
    name: str = Form(...),
    details: str = Form(default=""),
) -> HTMLResponse:
    state = await asyncio.to_thread(start_dataset, name, details)
    return HTMLResponse(render_dataset_panel(state))


@app.post("/dataset/stop", response_class=HTMLResponse)
async def dataset_stop() -> HTMLResponse:
    state = await asyncio.to_thread(stop_dataset)
    return HTMLResponse(render_dataset_panel(state))


@app.post("/dataset/send", response_class=HTMLResponse)
async def dataset_send() -> HTMLResponse:
    state = await asyncio.to_thread(send_dataset_to_storage)
    return HTMLResponse(render_dataset_panel(state))


@app.post("/dataset/reset", response_class=HTMLResponse)
async def dataset_reset() -> HTMLResponse:
    state = await asyncio.to_thread(reset_dataset)
    return HTMLResponse(render_dataset_panel(state))


@app.post("/control/{pi}/on", response_class=HTMLResponse)
async def turn_on(pi: str) -> HTMLResponse:
    ip = PI_IPS.get(pi)
    if not ip:
        return HTMLResponse(f"<p>Unknown Pi: {pi}</p>")
    try:
        ok, detail = await asyncio.to_thread(run_pi_systemctl, ip, "start")
        if ok:
            return HTMLResponse(f"✅ {pi} turned ON")
        return HTMLResponse(f"❌ Could not start {pi}: {detail}")
    except subprocess.SubprocessError as err:
        return HTMLResponse(f"❌ Failed to start {pi}: {err}")


@app.post("/control/{pi}/off", response_class=HTMLResponse)
async def turn_off(pi: str) -> HTMLResponse:
    ip = PI_IPS.get(pi)
    if not ip:
        return HTMLResponse(f"<p>Unknown Pi: {pi}</p>")
    try:
        ok, detail = await asyncio.to_thread(run_pi_systemctl, ip, "stop")
        if ok:
            return HTMLResponse(f"⛔ {pi} turned OFF")
        return HTMLResponse(f"❌ Could not stop {pi}: {detail}")
    except subprocess.SubprocessError as err:
        return HTMLResponse(f"❌ Failed to stop {pi}: {err}")


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "storage": "edge-1" if USE_EDGE_STORAGE else "pi-ssh",
        "auth": "basic" if is_auth_enabled() else "none",
    }


@app.get("/latest/{pi}", response_class=HTMLResponse)
async def latest_frame(
    pi: str,
    _t: int | None = Query(default=None),
) -> HTMLResponse:
    if pi not in PI_IPS:
        return HTMLResponse(f"<p>Unknown Pi: {pi}</p>")
    try:
        ip = PI_IPS[pi]
        local_path, capture_time, source_name = await asyncio.to_thread(
            fetch_latest_image, pi, ip, STATIC_DIR
        )
        if local_path is None and USE_EDGE_STORAGE:
            local_path, capture_time, source_name, err = await asyncio.to_thread(
                fetch_latest_from_storage, pi, STATIC_DIR
            )
            if local_path is None:
                return HTMLResponse(
                    f"<p>No frame from {pi}. Turn camera ON and wait a few seconds.</p>"
                    f"<p>{err}</p>"
                )
        elif local_path is None:
            return HTMLResponse(
                f"<p>No images found from {pi} yet. Is edge-client running?</p>"
            )
        cache_key = int(time.time() * 1000)
        if capture_time:
            time_label = capture_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_label = datetime.fromtimestamp(local_path.stat().st_mtime).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        return HTMLResponse(
            f'<img src="/static/{local_path.name}?v={cache_key}" alt="Latest from {pi}">'
            f'<p class="meta">Source: {source_name}<br>Capture: {time_label}</p>',
            headers={"Cache-Control": "no-store"},
        )
    except subprocess.SubprocessError:
        return HTMLResponse(f"<p>Could not reach {pi} over SSH.</p>")
    except Exception:
        return HTMLResponse(f"<p>Could not load image from {pi}.</p>")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
