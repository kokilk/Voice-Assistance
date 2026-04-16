"""
OAuth token persistence and refresh.
Tokens are stored in tokens/token.json (git-ignored).
"""
import json
import os
import stat
from pathlib import Path
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",   # needed for drafts().create()
    "https://www.googleapis.com/auth/contacts.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

_TOKEN_DIR = Path(__file__).parent.parent.parent / "tokens"
_TOKEN_FILE = _TOKEN_DIR / "token.json"


def _ensure_token_dir() -> None:
    _TOKEN_DIR.mkdir(exist_ok=True)
    # Lock down the directory so only the owner can read/write
    os.chmod(_TOKEN_DIR, stat.S_IRWXU)


def save_credentials(creds: Credentials) -> None:
    _ensure_token_dir()
    data = {
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes or SCOPES),
    }
    _TOKEN_FILE.write_text(json.dumps(data, indent=2))
    os.chmod(_TOKEN_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 600


def load_credentials() -> Optional[Credentials]:
    if not _TOKEN_FILE.exists():
        return None

    data = json.loads(_TOKEN_FILE.read_text())
    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes", SCOPES),
    )
    return creds


def get_valid_credentials() -> Optional[Credentials]:
    """Return valid (possibly refreshed) credentials, or None if not authed."""
    creds = load_credentials()
    if creds is None:
        return None

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
            return creds
        except Exception:
            # Refresh failed — user needs to re-authenticate
            clear_credentials()
            return None

    return None


def clear_credentials() -> None:
    if _TOKEN_FILE.exists():
        _TOKEN_FILE.unlink()


def get_user_email(creds: Credentials) -> Optional[str]:
    """Fetch the authenticated user's email via the userinfo endpoint."""
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {creds.token}"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            info = json.loads(resp.read())
            return info.get("email")
    except (urllib.error.URLError, json.JSONDecodeError):
        return None
