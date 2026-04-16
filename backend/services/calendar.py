"""
Google Calendar API wrapper.
All functions require valid credentials from token_store.get_valid_credentials().
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from backend.services.token_store import get_valid_credentials

_LOCAL_TZ = "America/Chicago"  # adjust to your timezone if needed


def _service():
    creds = get_valid_credentials()
    if creds is None:
        raise PermissionError("Not authenticated with Google. Visit /auth/login first.")
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _local_now() -> datetime:
    return datetime.now(ZoneInfo(_LOCAL_TZ))


def _day_bounds(dt: datetime) -> tuple[str, str]:
    start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end   = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _week_bounds(dt: datetime) -> tuple[str, str]:
    start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end   = start + timedelta(days=7)
    return start.isoformat(), end.isoformat()


def _fmt_event(ev: dict[str, Any]) -> dict[str, Any]:
    """Flatten a Google Calendar event into a simple dict."""
    start_raw = ev.get("start", {})
    end_raw   = ev.get("end", {})
    attendees = [
        a.get("email", "")
        for a in ev.get("attendees", [])
        if not a.get("self", False)
    ]
    return {
        "id":          ev.get("id", ""),
        "title":       ev.get("summary", "(no title)"),
        "start":       start_raw.get("dateTime") or start_raw.get("date", ""),
        "end":         end_raw.get("dateTime")   or end_raw.get("date", ""),
        "attendees":   attendees,
        "location":    ev.get("location"),
        "description": ev.get("description"),
        "html_link":   ev.get("htmlLink"),
    }


# ── Public API ──────────────────────────────────────────────────────────────

def list_events(
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """
    Return events between time_min and time_max (ISO 8601 strings).
    Defaults to today if neither is provided.
    """
    now = _local_now()
    if time_min is None:
        time_min, _ = _day_bounds(now)
    if time_max is None:
        _, time_max = _day_bounds(now)

    svc = _service()
    result = (
        svc.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return [_fmt_event(ev) for ev in result.get("items", [])]


def list_events_today() -> list[dict[str, Any]]:
    start, end = _day_bounds(_local_now())
    return list_events(time_min=start, time_max=end)


def list_events_week() -> list[dict[str, Any]]:
    start, end = _week_bounds(_local_now())
    return list_events(time_min=start, time_max=end)


def create_event(
    title: str,
    start: str,
    end: str,
    attendees: Optional[list[str]] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
) -> dict[str, Any]:
    """
    Create a calendar event. start/end are ISO 8601 strings with timezone.
    attendees is a list of email addresses.
    """
    body: dict[str, Any] = {
        "summary": title,
        "start":   {"dateTime": start, "timeZone": _LOCAL_TZ},
        "end":     {"dateTime": end,   "timeZone": _LOCAL_TZ},
    }
    if attendees:
        body["attendees"] = [{"email": e} for e in attendees]
    if description:
        body["description"] = description
    if location:
        body["location"] = location

    svc = _service()
    ev  = svc.events().insert(calendarId="primary", body=body, sendUpdates="all").execute()
    return _fmt_event(ev)


def update_event(
    event_id: str,
    title: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
) -> dict[str, Any]:
    """Patch an existing event. Only provided fields are changed."""
    svc = _service()
    existing = svc.events().get(calendarId="primary", eventId=event_id).execute()

    patch: dict[str, Any] = {}
    if title:
        patch["summary"] = title
    if start:
        patch["start"] = {"dateTime": start, "timeZone": _LOCAL_TZ}
    if end:
        patch["end"] = {"dateTime": end, "timeZone": _LOCAL_TZ}
    if description is not None:
        patch["description"] = description
    if location is not None:
        patch["location"] = location

    updated = (
        svc.events()
        .patch(calendarId="primary", eventId=event_id, body=patch, sendUpdates="all")
        .execute()
    )
    return _fmt_event(updated)


def delete_event(event_id: str) -> dict[str, str]:
    """Delete an event by ID."""
    svc = _service()
    # Fetch title first so we can confirm what was deleted
    ev = svc.events().get(calendarId="primary", eventId=event_id).execute()
    title = ev.get("summary", "(no title)")
    svc.events().delete(calendarId="primary", eventId=event_id, sendUpdates="all").execute()
    return {"deleted": True, "title": title, "event_id": event_id}


def check_conflicts(start: str, end: str) -> dict[str, Any]:
    """
    Check whether any event overlaps the given start/end window.
    Returns {"free": bool, "conflicts": [...events]}.
    """
    events = list_events(time_min=start, time_max=end, max_results=10)
    return {
        "free":      len(events) == 0,
        "conflicts": events,
    }


def search_events_by_title(query: str, days_ahead: int = 7) -> list[dict[str, Any]]:
    """Search upcoming events whose title contains query (case-insensitive)."""
    now = _local_now()
    end = now + timedelta(days=days_ahead)
    all_events = list_events(
        time_min=now.isoformat(),
        time_max=end.isoformat(),
        max_results=50,
    )
    q = query.lower()
    return [ev for ev in all_events if q in ev["title"].lower()]
