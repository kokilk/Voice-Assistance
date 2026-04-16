"""
Event routes — expose calendar data to the frontend.
"""
from fastapi import APIRouter, HTTPException
from backend.services import calendar as cal_svc

router = APIRouter()


def _auth_guard():
    from backend.services.token_store import get_valid_credentials
    if get_valid_credentials() is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Visit /auth/login to connect your Google account.",
        )


@router.get("/today")
async def events_today():
    """Return today's calendar events."""
    _auth_guard()
    try:
        events = cal_svc.list_events_today()
        return {"events": events, "count": len(events)}
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calendar error: {e}")


@router.get("/week")
async def events_week():
    """Return this week's calendar events."""
    _auth_guard()
    try:
        events = cal_svc.list_events_week()
        return {"events": events, "count": len(events)}
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calendar error: {e}")
