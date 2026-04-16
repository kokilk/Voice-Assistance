from pydantic import BaseModel
from typing import Optional


class CommandRequest(BaseModel):
    transcript: str


class CommandResponse(BaseModel):
    reply: str
    action_taken: Optional[str] = None


class EventSummary(BaseModel):
    id: str
    title: str
    start: str
    end: str
    attendees: list[str] = []
    location: Optional[str] = None
