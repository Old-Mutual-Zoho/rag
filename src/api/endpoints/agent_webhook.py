

import os
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status, Query, Request
from pydantic import BaseModel
from typing import Any, Dict, Optional
from src.integrations.slack.slack_chat_service import SlackChatService
import src.api.escalation as escalation_module

router = APIRouter()

# Slack config for testing
load_dotenv()
SLACK_TOKEN = os.getenv("SLACK_TOKEN", "")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "")

slack_service = SlackChatService(SLACK_TOKEN, SLACK_CHANNEL)


class AgentMessage(BaseModel):
    chat_id: str
    message: str
    sender: Optional[str] = "agent"
    agent_id: Optional[str] = None


@router.post("/agent/webhook", tags=["Agent"])
async def agent_webhook(msg: AgentMessage):
    """
    Webhook for agent to send a message to a client via Slack (for testing).
    """
    try:
        if msg.agent_id and escalation_module.state_manager:
            escalation_module.state_manager.mark_agent_joined(msg.chat_id, msg.agent_id)
        resp = slack_service.send_message(msg.chat_id, msg.message, sender=msg.sender)
        return {"success": True, "response": resp}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/agent/messages", tags=["Agent"])
async def get_agent_messages(chat_id: str = Query(..., description="Chat session ID")):
    """
    Fetch recent messages for a chat session (for agent polling, Slack version).
    """
    try:
        resp = slack_service.receive_messages(chat_id)
        return {"success": True, "messages": resp}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/agent/slack/events", tags=["Agent"])
async def slack_events(request: Request):
    """
    Slack Events API receiver.
    - Handles URL verification challenge.
    - Accepts message events from Slack so agents can type directly in Slack threads.
    """
    try:
        payload: Dict[str, Any] = await request.json()
        if payload.get("type") == "url_verification":
            return {"challenge": payload.get("challenge")}

        if payload.get("type") != "event_callback":
            return {"ok": True, "ignored": True}

        event = payload.get("event") or {}
        if event.get("type") != "message":
            return {"ok": True, "ignored": True}

        # Ignore non-thread messages and bot-generated events.
        if not event.get("thread_ts") or event.get("bot_id"):
            return {"ok": True, "ignored": True}

        # Optionally mark that an agent has joined when a human posts in the thread.
        chat_id = None
        text = event.get("text") or ""
        if "[chat_id:" in text and "]" in text:
            tag = text[text.find("[chat_id:") + 9 : text.find("]", text.find("[chat_id:"))]
            chat_id = tag.strip() or None

        if chat_id and escalation_module.state_manager and event.get("user"):
            escalation_module.state_manager.mark_agent_joined(chat_id, str(event.get("user")))

        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
