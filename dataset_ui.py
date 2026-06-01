"""HTML fragments for the dataset recording panel."""

from __future__ import annotations

from dataset_service import DatasetState


def render_dataset_panel(state: DatasetState) -> str:
    is_recording = state.status == "recording"
    is_stopped = state.status == "stopped"
    is_sent = state.status == "sent"
    is_idle = state.status == "idle"
    fields_disabled = "disabled" if is_recording or is_stopped or is_sent else ""
    name_value = _escape_attr(state.name)
    details_value = _escape_text(state.details)
    status_label = {
        "idle": "Ready",
        "recording": "Recording",
        "stopped": "Stopped — ready to send",
        "sent": "Sent to storage",
    }.get(state.status, state.status)
    message_html = ""
    if state.message:
        message_html = f'<p class="dataset-message">{_escape_text(state.message)}</p>'
    info_html = ""
    if state.started_at:
        info_html += f"<p class=\"meta\">Started: {_escape_text(state.started_at)}</p>"
    if state.stopped_at:
        info_html += f"<p class=\"meta\">Stopped: {_escape_text(state.stopped_at)}</p>"
    if state.frame_count is not None:
        info_html += f"<p class=\"meta\">Frames: {state.frame_count}</p>"
    if state.storage_path:
        info_html += (
            f"<p class=\"meta\">Storage: {_escape_text(state.storage_path)}</p>"
        )
    start_button = ""
    stop_button = ""
    send_button = ""
    new_button = ""
    if is_idle:
        start_button = (
            '<button type="submit" class="dataset-start">Make dataset</button>'
        )
    elif is_recording:
        stop_button = (
            '<button type="button" class="dataset-stop" '
            'hx-post="/dataset/stop" hx-target="#dataset-panel">'
            "Stop making dataset</button>"
        )
    elif is_stopped:
        send_button = (
            '<button type="button" class="dataset-send" '
            'hx-post="/dataset/send" hx-target="#dataset-panel" '
            'hx-indicator="#dataset-spinner" hx-disabled-elt="this" '
            'hx-timeout="600000">'
            "Send dataset to storage</button>"
        )
    elif is_sent:
        new_button = (
            '<button type="button" class="dataset-new" '
            'hx-post="/dataset/reset" hx-target="#dataset-panel">'
            "New dataset</button>"
        )
    form_html = ""
    if is_idle or is_recording:
        form_html = f"""
    <form class="dataset-form"
          hx-post="/dataset/start"
          hx-target="#dataset-panel"
          hx-trigger="submit">
        <label class="dataset-label" for="dataset-name">Dataset name</label>
        <input id="dataset-name" name="name" type="text"
               placeholder="e.g. ball-drop-run-1"
               value="{name_value}" {fields_disabled} required>
        <label class="dataset-label" for="dataset-details">Details</label>
        <textarea id="dataset-details" name="details" rows="3"
                  placeholder="Notes: lighting, object, experiment setup..."
                  {fields_disabled}>{details_value}</textarea>
        {start_button}
    </form>"""
    elif is_stopped:
        form_html = f"""
    <div class="dataset-form">
        <p class="meta"><strong>{_escape_text(state.name)}</strong> — {_escape_text(state.details)}</p>
    </div>"""
    return f"""
<div class="dataset-panel-inner">
    <h2>Dataset</h2>
    <p class="meta">Record frames from all running cameras into one combined dataset.</p>
    <p class="dataset-status">Status: <strong>{status_label}</strong></p>
    {message_html}
    {info_html}
    {form_html}
    {stop_button}
    {send_button}
    {new_button}
    <span id="dataset-spinner" class="htmx-indicator">Uploading…</span>
</div>
"""


def _escape_text(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _escape_attr(value: str) -> str:
    return _escape_text(value)
