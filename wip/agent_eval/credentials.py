"""Credential structure checks shared by the launcher and Pier agent."""

from __future__ import annotations

import json
from pathlib import Path


def has_kimi_login_material(home: Path) -> bool:
    """Return whether a Kimi home contains non-empty OAuth credential material."""

    oauth_file = home / "oauth" / "kimi-code"
    try:
        if oauth_file.is_file() and oauth_file.read_bytes().strip():
            return True
    except OSError:
        pass

    credentials_file = home / "credentials" / "kimi-code.json"
    try:
        credentials = json.loads(credentials_file.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(credentials, dict):
        return False
    return any(
        isinstance(credentials.get(field), str) and bool(credentials[field].strip())
        for field in ("access_token", "refresh_token")
    )


def resolve_kimi_auth_home(explicit: str | None = None) -> Path | None:
    """Resolve a Kimi home only when it contains structurally usable credentials."""

    home = Path(explicit).expanduser() if explicit else Path.home() / ".kimi-code"
    if explicit and not home.is_dir():
        raise ValueError(
            f"KIMI_AUTH_HOME_PATH points to a missing directory: {explicit}"
        )
    if not home.is_dir():
        return None
    if has_kimi_login_material(home):
        return home
    if explicit:
        raise ValueError(
            "KIMI_AUTH_HOME_PATH does not contain non-empty Kimi login "
            f"credentials: {explicit}"
        )
    return None


def require_kimi_auth_home(explicit: str | None = None) -> Path:
    """Require a structurally valid Kimi login without exposing credential values."""

    home = resolve_kimi_auth_home(explicit)
    if home is None:
        raise ValueError(
            "Missing Agent credentials: ~/.kimi-code login credential with a "
            "non-empty access or refresh token; run `kimi login`"
        )
    return home
