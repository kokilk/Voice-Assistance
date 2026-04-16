"""
Google OAuth 2.0 routes.
Endpoints: /auth/login  /auth/callback  /auth/status  /auth/logout
"""
import os
import secrets
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow

from backend.services.token_store import (
    SCOPES,
    clear_credentials,
    get_user_email,
    get_valid_credentials,
    save_credentials,
)

router = APIRouter()

# In-memory state store — maps state token → flow object so the
# code_verifier generated at login is available at callback.
_oauth_states: dict[str, Flow] = {}

CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")
FRONTEND_URL  = os.getenv("FRONTEND_ORIGIN", "http://localhost:8000")


def _build_flow() -> Flow:
    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth credentials not set. Copy .env.example to .env and fill in GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )

    client_config = {
        "web": {
            "client_id":                CLIENT_ID,
            "client_secret":            CLIENT_SECRET,
            "redirect_uris":            [REDIRECT_URI],
            "auth_uri":                 "https://accounts.google.com/o/oauth2/auth",
            "token_uri":                "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    return flow


# ── GET /auth/status ────────────────────────────────────────────────────────
@router.get("/status")
async def auth_status() -> dict:
    """Check whether the user has valid Google credentials."""
    creds = get_valid_credentials()
    if creds is None:
        return {"authenticated": False, "email": None}

    email = get_user_email(creds)
    return {"authenticated": True, "email": email}


# ── GET /auth/login ─────────────────────────────────────────────────────────
@router.get("/login")
async def login() -> RedirectResponse:
    """Redirect the browser to Google's OAuth consent screen."""
    flow = _build_flow()

    state = secrets.token_urlsafe(32)

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",          # force refresh_token every time
        state=state,
    )

    # Store the flow object (not just True) so the code_verifier
    # generated here is reused during token exchange in /callback.
    _oauth_states[state] = flow

    return RedirectResponse(url=auth_url)


# ── GET /auth/callback ──────────────────────────────────────────────────────
@router.get("/callback")
async def callback(
    code:  Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
) -> RedirectResponse:
    """Handle the OAuth callback, exchange code for tokens, then redirect home."""
    if error:
        return RedirectResponse(url=f"{FRONTEND_URL}?auth=error&reason={error}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter.")

    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid OAuth state. Possible CSRF attempt.")

    # Reuse the same flow from login so the code_verifier is preserved.
    flow = _oauth_states.pop(state)
    flow.fetch_token(code=code)

    save_credentials(flow.credentials)

    return RedirectResponse(url=f"{FRONTEND_URL}?auth=success")


# ── POST /auth/logout ────────────────────────────────────────────────────────
@router.post("/logout")
async def logout() -> dict:
    """Delete stored tokens and sign the user out."""
    clear_credentials()
    return {"authenticated": False, "message": "Signed out successfully."}
