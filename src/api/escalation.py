from fastapi import APIRouter, Request
from src.chatbot.state_manager import StateManager

router = APIRouter()


# Will be set by main.py after import
state_manager: StateManager = None


@router.post("/escalate")
async def escalate(request: Request):
    data = await request.json()
    session_id = data.get("session_id")
    if not session_id:
        return {"success": False, "error": "Missing session_id"}
    # Set in-memory escalation flag
    state_manager.update_session(session_id, {"escalated": True})
    return {"success": True, "escalated": True}
