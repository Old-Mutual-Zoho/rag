

import os
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel
from typing import Optional
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
