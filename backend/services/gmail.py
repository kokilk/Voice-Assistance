"""
Gmail API wrapper — send calendar invite emails.
"""
from __future__ import annotations

import base64
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from googleapiclient.discovery import build

from backend.services.token_store import get_valid_credentials, get_user_email


def _service():
    creds = get_valid_credentials()
    if creds is None:
        raise PermissionError("Not authenticated with Google. Visit /auth/login first.")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _sender_email() -> str:
    creds = get_valid_credentials()
    return get_user_email(creds) or "me"


def send_invite(
    to_email: str,
    subject: str,
    body_text: str,
    event_title: Optional[str] = None,
    event_start: Optional[str] = None,
    event_link: Optional[str] = None,
) -> dict[str, str]:
    """
    Send a plain-text invite email via Gmail.

    Args:
        to_email:    Recipient email address.
        subject:     Email subject line.
        body_text:   Main body text (plain).
        event_title: Optional event name to include in the body.
        event_start: Optional start time string.
        event_link:  Optional Google Calendar link.

    Returns:
        dict with message id and thread id.
    """
    sender = _sender_email()

    # Build plain-text body
    lines = [body_text.strip()]
    if event_title:
        lines += ["", f"Event: {event_title}"]
    if event_start:
        lines += [f"When:  {event_start}"]
    if event_link:
        lines += [f"Link:  {event_link}"]

    full_body = "\n".join(lines)

    msg = MIMEMultipart("alternative")
    msg["From"]    = sender
    msg["To"]      = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(full_body, "plain"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    svc     = _service()
    result  = svc.users().messages().send(userId="me", body={"raw": raw}).execute()

    return {
        "sent":      True,
        "message_id": result.get("id", ""),
        "thread_id":  result.get("threadId", ""),
        "to":         to_email,
        "subject":    subject,
    }


def send_email(
    to_email: str,
    subject: str,
    body_text: str,
) -> dict[str, str]:
    """
    Send a plain-text email via Gmail.

    Args:
        to_email:  Recipient email address.
        subject:   Email subject line.
        body_text: Body of the email.

    Returns:
        dict with sent status, message id, and thread id.
    """
    sender = _sender_email()

    msg = MIMEMultipart("alternative")
    msg["From"]    = sender
    msg["To"]      = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text.strip(), "plain"))

    raw    = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    svc    = _service()
    result = svc.users().messages().send(userId="me", body={"raw": raw}).execute()

    return {
        "sent":       True,
        "message_id": result.get("id", ""),
        "thread_id":  result.get("threadId", ""),
        "to":         to_email,
        "subject":    subject,
    }


def create_draft(
    to_email: str,
    subject: str,
    body_text: str,
) -> dict[str, str]:
    """
    Save an email as a Gmail draft (does not send).

    Args:
        to_email:  Recipient email address.
        subject:   Email subject line.
        body_text: Body of the draft email.

    Returns:
        dict with draft id and status.
    """
    sender = _sender_email()

    msg = MIMEMultipart("alternative")
    msg["From"]    = sender
    msg["To"]      = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text.strip(), "plain"))

    raw    = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    svc    = _service()
    result = svc.users().drafts().create(
        userId="me",
        body={"message": {"raw": raw}},
    ).execute()

    return {
        "drafted":  True,
        "draft_id": result.get("id", ""),
        "to":       to_email,
        "subject":  subject,
    }
