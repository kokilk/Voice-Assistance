"""
Google People API wrapper — search contacts by name.
"""
from __future__ import annotations

from typing import Any

from googleapiclient.discovery import build

from backend.services.token_store import get_valid_credentials


def _service():
    creds = get_valid_credentials()
    if creds is None:
        raise PermissionError("Not authenticated with Google. Visit /auth/login first.")
    return build("people", "v1", credentials=creds, cache_discovery=False)


def search_contacts(name: str, max_results: int = 5) -> list[dict[str, Any]]:
    """
    Search Google Contacts for people whose name matches the query.
    Returns a list of {name, email, phone} dicts.
    """
    svc = _service()

    # searchContacts API (requires contacts.readonly scope)
    result = (
        svc.people()
        .searchContacts(
            query=name,
            readMask="names,emailAddresses,phoneNumbers",
            pageSize=max_results,
        )
        .execute()
    )

    contacts = []
    for item in result.get("results", []):
        person = item.get("person", {})

        display_name = ""
        names = person.get("names", [])
        if names:
            display_name = names[0].get("displayName", "")

        email = ""
        emails = person.get("emailAddresses", [])
        if emails:
            email = emails[0].get("value", "")

        phone = ""
        phones = person.get("phoneNumbers", [])
        if phones:
            phone = phones[0].get("value", "")

        if display_name or email:
            contacts.append({"name": display_name, "email": email, "phone": phone})

    return contacts
