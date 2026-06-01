"""Optional HTTP Basic Auth for the dashboard."""

from __future__ import annotations

import base64
import secrets
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from config import DASHBOARD_PASSWORD, DASHBOARD_USERNAME


def is_auth_enabled() -> bool:
    return bool(DASHBOARD_PASSWORD)


def credentials_are_valid(username: str, password: str) -> bool:
    user_ok = secrets.compare_digest(username, DASHBOARD_USERNAME)
    pass_ok = secrets.compare_digest(password, DASHBOARD_PASSWORD)
    return user_ok and pass_ok


def parse_basic_auth_header(header_value: str) -> tuple[str, str] | None:
    if not header_value.lower().startswith("basic "):
        return None
    try:
        decoded = base64.b64decode(header_value[6:].strip()).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    if ":" not in decoded:
        return None
    username, password = decoded.split(":", 1)
    return username, password


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not is_auth_enabled():
            return await call_next(request)
        auth_header = request.headers.get("Authorization", "")
        parsed = parse_basic_auth_header(auth_header)
        if parsed is None:
            return _unauthorized_response()
        username, password = parsed
        if not credentials_are_valid(username, password):
            return _unauthorized_response()
        return await call_next(request)


def _unauthorized_response() -> Response:
    return Response(
        content="Authentication required",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="gizzagawk dashboard"'},
    )
