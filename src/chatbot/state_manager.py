"""
Session and state management for chatbot
"""

from typing import Dict, Optional, Any
from datetime import datetime
import uuid


class StateManager:
    def __init__(self, redis_cache, postgres_db):
        self.redis = redis_cache
        self.db = postgres_db

    def create_session(self, user_id: str, mode: str = "conversational") -> str:
        """Create new session"""
        session_id = str(uuid.uuid4())

        # Create in PostgreSQL
        conversation = self.db.create_conversation(user_id, mode)

        # Initialize in Redis
        session_data = {
            "session_id": session_id,
            "conversation_id": str(conversation.id),
            "user_id": user_id,
            "mode": mode,
            "current_flow": None,
            "current_step": 0,
            "collected_data": {},
            "context": {},
            "created_at": datetime.utcnow().isoformat(),
        }

        self.redis.set_session(session_id, session_data, ttl=1800)

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        return self.redis.get_session(session_id)

    def update_session(self, session_id: str, updates: Dict[str, Any]):
        """Update session data"""
        self.redis.update_session(session_id, updates)

    def switch_mode(self, session_id: str, new_mode: str, flow: str = None):
        """Switch between conversational and guided mode"""
        updates = {"mode": new_mode, "current_flow": flow, "current_step": 0 if new_mode == "guided" else None}
        self.update_session(session_id, updates)

    def advance_step(self, session_id: str, collected_data: Dict[str, Any] = None):
        """Advance to next step in guided flow"""
        session = self.get_session(session_id)
        if session:
            updates = {"current_step": session["current_step"] + 1}
            if collected_data:
                session["collected_data"].update(collected_data)
                updates["collected_data"] = session["collected_data"]

            self.update_session(session_id, updates)

    def set_flow(self, session_id: str, flow_name: str):
        """Set current flow"""
        self.update_session(session_id, {"current_flow": flow_name, "current_step": 0})

    def get_collected_data(self, session_id: str) -> Dict[str, Any]:
        """Get all collected data from current flow"""
        session = self.get_session(session_id)
        return session.get("collected_data", {}) if session else {}

    def clear_collected_data(self, session_id: str):
        """Clear collected data"""
        self.update_session(session_id, {"collected_data": {}})

    def end_session(self, session_id: str):
        """End session and clean up"""
        session = self.get_session(session_id)
        if session:
            # Update conversation end time in PostgreSQL
            # conversation = self.db.get_conversation(session['conversation_id'])
            # conversation.ended_at = datetime.utcnow()
            # self.db.save(conversation)

            # Delete from Redis
            self.redis.delete_session(session_id)
