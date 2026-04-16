"""
7 tool definitions for the Claude agent + call_tool dispatcher.
Each tool maps directly to a service function from Phase 3.
"""
from __future__ import annotations

import json
from typing import Any

# ── Tool schemas (sent to Claude) ───────────────────────────────────────────

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "list_events",
        "description": (
            "List calendar events in a time range. "
            "Use this to answer 'what do I have today/tomorrow/this week' questions. "
            "time_min and time_max are ISO 8601 strings (e.g. '2026-04-14T00:00:00-05:00'). "
            "Omit both to get today's events."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_min": {
                    "type": "string",
                    "description": "Start of range (ISO 8601). Defaults to start of today.",
                },
                "time_max": {
                    "type": "string",
                    "description": "End of range (ISO 8601). Defaults to end of today.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max events to return (default 20).",
                    "default": 20,
                },
            },
            "required": [],
        },
    },
    {
        "name": "create_event",
        "description": (
            "Create a new calendar event. "
            "Always run check_conflicts first to warn the user if the slot is busy. "
            "start and end are ISO 8601 strings with timezone offset. "
            "attendees is a list of email addresses. "
            "Include a call link or phone number in description when setting up a call."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title":       {"type": "string",  "description": "Event title."},
                "start":       {"type": "string",  "description": "Start time (ISO 8601)."},
                "end":         {"type": "string",  "description": "End time (ISO 8601). Default 1 hour after start."},
                "attendees":   {"type": "array",   "items": {"type": "string"}, "description": "List of attendee email addresses."},
                "description": {"type": "string",  "description": "Event notes, agenda, or call link."},
                "location":    {"type": "string",  "description": "Physical location or video URL."},
            },
            "required": ["title", "start", "end"],
        },
    },
    {
        "name": "update_event",
        "description": (
            "Update an existing calendar event by its ID. "
            "Only include fields you want to change. "
            "Use list_events to find the event_id first if you don't have it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id":    {"type": "string", "description": "Google Calendar event ID."},
                "title":       {"type": "string", "description": "New event title."},
                "start":       {"type": "string", "description": "New start time (ISO 8601)."},
                "end":         {"type": "string", "description": "New end time (ISO 8601)."},
                "description": {"type": "string", "description": "New description."},
                "location":    {"type": "string", "description": "New location."},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "delete_event",
        "description": (
            "Delete a calendar event by its ID. "
            "Always state the event title in your reply so the user knows what was removed. "
            "Use list_events to find the event_id if you don't have it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "Google Calendar event ID to delete."},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "check_conflicts",
        "description": (
            "Check whether a proposed time slot is free or has conflicting events. "
            "Call this before creating any event."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Proposed start time (ISO 8601)."},
                "end":   {"type": "string", "description": "Proposed end time (ISO 8601)."},
            },
            "required": ["start", "end"],
        },
    },
    {
        "name": "search_contacts",
        "description": (
            "Search the user's Google Contacts by name. "
            "Returns name and email address. "
            "Use this to resolve 'schedule a meeting with John' into an email address."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name or partial name to search for."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "send_invite",
        "description": (
            "Send a Gmail invite email to an attendee. "
            "Use this after creating an event to notify people who weren't auto-invited."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to_email":    {"type": "string", "description": "Recipient email address."},
                "subject":     {"type": "string", "description": "Email subject line."},
                "body_text":   {"type": "string", "description": "Body of the invite email."},
                "event_title": {"type": "string", "description": "Event name to include."},
                "event_start": {"type": "string", "description": "Human-readable start time."},
                "event_link":  {"type": "string", "description": "Google Calendar link to the event."},
            },
            "required": ["to_email", "subject", "body_text"],
        },
    },
    {
        "name": "send_email",
        "description": (
            "Send a general email via Gmail. "
            "Use for any email that is not a calendar invite — e.g. follow-ups, notes, messages. "
            "Use search_contacts first to resolve a name to an email address."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to_email":  {"type": "string", "description": "Recipient email address."},
                "subject":   {"type": "string", "description": "Email subject line."},
                "body_text": {"type": "string", "description": "Body of the email (plain text)."},
            },
            "required": ["to_email", "subject", "body_text"],
        },
    },
    {
        "name": "create_draft",
        "description": (
            "Save an email as a Gmail draft without sending it. "
            "Use when the user says 'draft an email' or 'write an email but don't send it yet'. "
            "Use search_contacts first to resolve a name to an email address."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to_email":  {"type": "string", "description": "Recipient email address."},
                "subject":   {"type": "string", "description": "Email subject line."},
                "body_text": {"type": "string", "description": "Body of the draft email (plain text)."},
            },
            "required": ["to_email", "subject", "body_text"],
        },
    },
]


# ── Dispatcher ───────────────────────────────────────────────────────────────

def call_tool(name: str, inputs: dict[str, Any]) -> Any:
    """
    Route a tool call from Claude to the correct service function.
    Returns a JSON-serialisable result.
    """
    from backend.services import calendar as cal
    from backend.services.gmail import send_invite, send_email, create_draft
    from backend.services.contacts import search_contacts

    try:
        if name == "list_events":
            return cal.list_events(
                time_min=inputs.get("time_min"),
                time_max=inputs.get("time_max"),
                max_results=inputs.get("max_results", 20),
            )

        if name == "create_event":
            return cal.create_event(
                title=inputs["title"],
                start=inputs["start"],
                end=inputs["end"],
                attendees=inputs.get("attendees"),
                description=inputs.get("description"),
                location=inputs.get("location"),
            )

        if name == "update_event":
            return cal.update_event(
                event_id=inputs["event_id"],
                title=inputs.get("title"),
                start=inputs.get("start"),
                end=inputs.get("end"),
                description=inputs.get("description"),
                location=inputs.get("location"),
            )

        if name == "delete_event":
            return cal.delete_event(event_id=inputs["event_id"])

        if name == "check_conflicts":
            return cal.check_conflicts(start=inputs["start"], end=inputs["end"])

        if name == "search_contacts":
            return search_contacts(name=inputs["name"])

        if name == "send_invite":
            return send_invite(
                to_email=inputs["to_email"],
                subject=inputs["subject"],
                body_text=inputs["body_text"],
                event_title=inputs.get("event_title"),
                event_start=inputs.get("event_start"),
                event_link=inputs.get("event_link"),
            )

        if name == "send_email":
            return send_email(
                to_email=inputs["to_email"],
                subject=inputs["subject"],
                body_text=inputs["body_text"],
            )

        if name == "create_draft":
            return create_draft(
                to_email=inputs["to_email"],
                subject=inputs["subject"],
                body_text=inputs["body_text"],
            )

        return {"error": f"Unknown tool: {name}"}

    except PermissionError as e:
        return {"error": str(e)}
    except KeyError as e:
        return {"error": f"Missing required argument: {e}"}
    except Exception as e:
        return {"error": f"Tool '{name}' failed: {e}"}
