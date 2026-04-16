"""
Centralised configuration and startup validation.
Imported by main.py on boot — fails fast with a clear message if
required environment variables are missing.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    frontend_origin: str
    port: int


_REQUIRED = {
    "ANTHROPIC_API_KEY":    "Your Anthropic API key (starts with sk-ant-…)",
    "GOOGLE_CLIENT_ID":     "OAuth 2.0 client ID from Google Cloud Console",
    "GOOGLE_CLIENT_SECRET": "OAuth 2.0 client secret from Google Cloud Console",
}

_OPTIONAL = {
    "GOOGLE_REDIRECT_URI": "http://localhost:8000/auth/callback",
    "FRONTEND_ORIGIN":     "http://localhost:8000",
    "PORT":                "8000",
}


def load_config(strict: bool = True) -> Config:
    """
    Load and validate environment variables.

    Args:
        strict: If True, exit with a clear error message when required
                vars are missing. If False, return a config with empty
                strings for missing required vars (useful for testing).
    """
    missing = [k for k in _REQUIRED if not os.getenv(k, "").strip()]

    if missing and strict:
        lines = [
            "",
            "  ╔══════════════════════════════════════════════════╗",
            "  ║  K — Missing required environment variables      ║",
            "  ╚══════════════════════════════════════════════════╝",
            "",
            "  Copy .env.example to .env and fill in the values below:",
            "",
        ]
        for key in missing:
            lines.append(f"    {key}")
            lines.append(f"      → {_REQUIRED[key]}")
            lines.append("")
        lines.append("  Then restart the server.")
        lines.append("")
        print("\n".join(lines), file=sys.stderr)
        sys.exit(1)

    return Config(
        anthropic_api_key    = os.getenv("ANTHROPIC_API_KEY", ""),
        google_client_id     = os.getenv("GOOGLE_CLIENT_ID", ""),
        google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET", ""),
        google_redirect_uri  = os.getenv("GOOGLE_REDIRECT_URI", _OPTIONAL["GOOGLE_REDIRECT_URI"]),
        frontend_origin      = os.getenv("FRONTEND_ORIGIN",     _OPTIONAL["FRONTEND_ORIGIN"]),
        port                 = int(os.getenv("PORT", _OPTIONAL["PORT"])),
    )


# Module-level singleton — other modules import this
# We use strict=False so that importing during tests doesn't sys.exit.
# main.py calls load_config(strict=True) explicitly on startup.
settings: Config | None = None


def get_settings() -> Config:
    global settings
    if settings is None:
        settings = load_config(strict=False)
    return settings
