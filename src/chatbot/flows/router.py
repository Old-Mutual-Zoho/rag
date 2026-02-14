"""
Chat router - Determines mode and routes messages
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ChatRouter:
    def __init__(self, conversational_mode, guided_mode, state_manager, product_matcher):
        self.conversational = conversational_mode
        self.guided = guided_mode
        self.state_manager = state_manager
        self.product_matcher = product_matcher

    async def route(
        self,
        message: str,
        session_id: str,
        user_id: str,
        form_data: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """Route message to appropriate mode. form_data is used as user_input in guided flows when set."""

        # Get session state
        session = self.state_manager.get_session(session_id)

        if not session:
            # Create new session
            session_id = self.state_manager.create_session(user_id)
            session = self.state_manager.get_session(session_id)

        # For exit intent we need the raw message
        effective_message = (message or "").strip() if form_data is None else ""
        if self._is_exit_intent(effective_message or str(message)) and session.get("mode") == "guided":
            self.state_manager.switch_mode(session_id, "conversational")
            return {"message": "👋 Exited guided flow. How else can I help you?", "mode": "conversational"}

        # Button actions from the frontend to start guided mode and immediately return the first form/cards.
        # This is used for digital products where the user clicks "Get quotation".
        if form_data and isinstance(form_data, dict):
            action = str(form_data.get("action") or "").strip().lower()

            if action in ("get_quotation", "get_quote"):
                ctx = (session.get("context") or {}) if isinstance(session, dict) else {}
                topic = (ctx.get("product_topic") or {}) if isinstance(ctx, dict) else {}
                product_flow = topic.get("digital_flow")
                initial_data = {"product_flow": product_flow} if product_flow else None
                return await self.guided.start_flow("journey", session_id, user_id, initial_data=initial_data)

            if action == "start_guided":
                flow_name = form_data.get("flow") or form_data.get("flow_name") or "journey"
                initial_data = form_data.get("initial_data") or {}
                return await self.guided.start_flow(str(flow_name), session_id, user_id, initial_data=initial_data)

        # If in guided mode, stay in guided unless exiting
        if session.get("mode") == "guided" and session.get("current_flow"):
            user_input = form_data if form_data is not None else message
            return await self.guided.process(user_input, session_id, user_id)

        # Check for guided flow triggers (only when no form_data)
        if form_data is None and self._is_guided_trigger(message):
            flow_type = self._detect_flow_type(message)
            initial_data = None
            if flow_type in ("personal_accident", "travel_insurance", "motor_private", "serenicare"):
                initial_data = {"product_flow": flow_type}

            logger.info(
                "[Router] Guided trigger detected: message='%s' flow_type=%s initial_data=%s",
                message[:100], flow_type, initial_data
            )

            # Always start the journey engine for guided triggers.
            return await self.guided.start_flow("journey", session_id, user_id, initial_data=initial_data)

        # Default to conversational mode
        return await self.conversational.process(message, session_id, user_id, form_data=form_data)

    def _is_guided_trigger(self, message: str) -> bool:
        """Check if message should trigger guided flow"""
        message_lower = message.lower()

        # Explicit quotation/application requests
        explicit_triggers = [
            "get a quote",
            "get a quotation",
            "get quotation",
            "want a quote",
            "want a quotation",
            "want quotation",
            "need a quote",
            "need a quotation",
            "i want to apply",
            "i want to buy",
            "i want to purchase",
            "can i get a quote",
            "can i get a quotation",
            "can i get quotation",
            "give me a quote",
            "provide a quote",
        ]

        if any(trigger in message_lower for trigger in explicit_triggers):
            logger.info("[Router] Explicit guided trigger matched: %s", message[:100])
            return True

        # General keywords that might indicate quotation intent
        general_triggers = [
            "quote",
            "quotation",
            "buy",
            "apply",
            "purchase",
            "how much",
            "price",
            "cost",
            "premium",
        ]
        matched = any(trigger in message_lower for trigger in general_triggers)
        if matched:
            logger.info("[Router] General guided trigger matched: %s", message[:100])
        return matched

    def _detect_flow_type(self, message: str) -> str:
        """Detect which guided flow to start"""
        message_lower = message.lower()

        # Personal Accident: apply, buy, get cover for personal accident
        if any(phrase in message_lower for phrase in ["personal accident", "pa insurance", "accident cover", "pa cover"]):
            return "personal_accident"

        # Travel Insurance: travel insurance, travel sure, travel cover
        if any(phrase in message_lower for phrase in ["travel insurance", "travel sure", "travel cover", "travel policy"]):
            return "travel_insurance"

        # Motor Private: car, vehicle, motor insurance
        if any(
            phrase in message_lower
            for phrase in [
                "motor private",
                "motor insurance",
                "car insurance",
                "vehicle insurance",
                "motor cover",
                "car cover",
            ]
        ):
            return "motor_private"

        # Serenicare: health, medical, serenicare
        if any(
            phrase in message_lower
            for phrase in [
                "serenicare",
                "health insurance",
                "medical cover",
                "medical insurance",
                "health cover",
                "family health",
            ]
        ):
            return "serenicare"

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
