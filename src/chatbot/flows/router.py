"""
Chat router - Determines mode and routes messages
"""

from typing import Dict


class ChatRouter:
    def __init__(self, conversational_mode, guided_mode, state_manager, product_matcher):
        self.conversational = conversational_mode
        self.guided = guided_mode
        self.state_manager = state_manager
        self.product_matcher = product_matcher

    async def route(self, message: str, session_id: str, user_id: str) -> Dict:
        """Route message to appropriate mode"""

        # Get session state
        session = self.state_manager.get_session(session_id)

        if not session:
            # Create new session
            session_id = self.state_manager.create_session(user_id)
            session = self.state_manager.get_session(session_id)

        # Check for exit intent (leave guided mode)
        if self._is_exit_intent(message) and session.get("mode") == "guided":
            self.state_manager.switch_mode(session_id, "conversational")
            return {"message": "👋 Exited guided flow. How else can I help you?", "mode": "conversational"}

        # If in guided mode, stay in guided unless exiting
        if session.get("mode") == "guided" and session.get("current_flow"):
            return await self.guided.process(message, session_id, user_id)

        # Check for guided flow triggers
        if self._is_guided_trigger(message):
            flow_type = self._detect_flow_type(message)
            return await self.guided.start_flow(flow_type, session_id, user_id)

        # Default to conversational mode
        return await self.conversational.process(message, session_id, user_id)

    def _is_guided_trigger(self, message: str) -> bool:
        """Check if message should trigger guided flow"""
        triggers = ["quote", "buy", "apply", "purchase", "get insurance", "how much", "price", "cost", "premium", "i want", "i need", "help me choose"]

        message_lower = message.lower()
        return any(trigger in message_lower for trigger in triggers)

    def _detect_flow_type(self, message: str) -> str:
        """Detect which guided flow to start"""
        message_lower = message.lower()

        # Quote/buy triggers
        if any(word in message_lower for word in ["quote", "how much", "price", "cost"]):
            return "quotation"

        # Discovery triggers
        if any(word in message_lower for word in ["help me choose", "recommend", "which"]):
            return "discovery"

        # Default to discovery
        return "discovery"

    def _is_exit_intent(self, message: str) -> bool:
        """Check if user wants to exit guided flow"""
        exits = ["exit", "cancel", "stop", "go back", "start over", "nevermind", "not now"]

        message_lower = message.lower()
        return any(exit in message_lower for exit in exits)
