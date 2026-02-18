"""Response processing utilities.

This module integrates follow-up detection, incomplete input checks and fallback triggering.
"""
from typing import Any, Dict, Optional
import re
import logging

from .followup_manager import FollowUpManager
from .fallback_handler import FallbackHandler
from .error_handler import ErrorHandler

logger = logging.getLogger(__name__)


class ResponseProcessor:
    """Process raw responses from the RAG/LLM layer and determine next actions.

    Responsibilities:
    - Detect follow-up questions contained in the model response.
    - Detect incomplete or ambiguous user input and ask clarifying questions.
    - Trigger fallback handling when confidence is low or no useful answer exists.
    - Normalize final output to a consistent dict the rest of the app can consume.

    Supports persisting follow-ups into the provided StateManager (session store).
    """

    DEFAULT_CONFIDENCE_THRESHOLD = 0.35

    def __init__(self,
                 followup_manager: Optional[FollowUpManager] = None,
                 fallback_handler: Optional[FallbackHandler] = None,
                 error_handler: Optional[ErrorHandler] = None,
                 state_manager: Optional[Any] = None):
        self.followup_manager = followup_manager or FollowUpManager()
        self.fallback_handler = fallback_handler or FallbackHandler()
        self.error_handler = error_handler or ErrorHandler()
        # Optional StateManager (provides get_session/update_session for persistent session storage)
        self.state_manager = state_manager

    def process_response(
        self,
        raw_response: str,
        user_input: str,
        confidence: float,
        conversation_state: Dict[str, Any],
        *,
        session_id: Optional[str] = None,
        products_matched: Optional[list] = None,
    ) -> Dict[str, Any]:
        """Return a normalized dict with keys: message, follow_up (optional), fallback (optional), metadata.

        If state_manager and session_id are provided follow-ups will be queued into the persistent session store.
        When products_matched is provided (e.g. ["Serenicare"]), short queries that match a product name
        are not treated as incomplete, so the RAG answer is returned instead of a clarifying question.
        """
        try:
            logger.debug("Processing response: confidence=%s, user_input=%s", confidence, user_input)

            # Basic sanitation
            message = (raw_response or "").strip()

            # Detect errors or model failure signatures
            if not message or message.lower().startswith("error"):
                logger.warning("Empty or error-like model response detected")
                payload = self.fallback_handler.generate_fallback(user_input, reason="empty_or_error", conversation_state=conversation_state)
                # Persist fallback into session store if available
                if self.state_manager and session_id:
                    self.state_manager.update_session(session_id, {"fallbacks": conversation_state.get("fallbacks", [])})
                return payload

            # If user input looks incomplete, ask a clarifying question — unless the query
            # matches a product we already resolved (e.g. user typed "serenicare" and we have Serenicare).
            # Also skip this check if products_matched list is populated, since that means we found relevant products.
            has_matched_products = products_matched is not None and len(products_matched) > 0
            query_matches = self._query_matches_product(user_input, products_matched)

            if self._is_incomplete_input(user_input) and not has_matched_products and not query_matches:
                logger.info(
                    "Incomplete input detected: user_input='%s', has_products=%s, query_matches=%s",
                    user_input, has_matched_products, query_matches
                )
                question = self.followup_manager.create_clarifying_question(user_input)
                # Persist followup in session if possible
                if self.state_manager and session_id:
                    self.followup_manager.queue_followup_session(session_id, self.state_manager, question)
                else:
                    self.followup_manager.queue_followup(conversation_state, question)
                return {
                    "message": question,
                    "follow_up": True,
                    "fallback": False,
                    "metadata": {"reason": "incomplete_input"},
                }

            # Low confidence => fallback
            if confidence is not None and confidence < self.DEFAULT_CONFIDENCE_THRESHOLD:
                logger.info("Low confidence (%.2f) - triggering fallback", confidence)
                payload = self.fallback_handler.generate_fallback(user_input, confidence=confidence, conversation_state=conversation_state)
                if self.state_manager and session_id:
                    self.state_manager.update_session(session_id, {"fallbacks": conversation_state.get("fallbacks", [])})
                return payload

            # Detect whether model response contains a follow-up question for the user
            if self._contains_follow_up_question(message):
                question_text = self.followup_manager.extract_followup_from_text(message)
                if self.state_manager and session_id:
                    self.followup_manager.queue_followup_session(session_id, self.state_manager, question_text)
                else:
                    self.followup_manager.queue_followup(conversation_state, question_text)
                return {
                    "message": message,
                    "follow_up": True,
                    "fallback": False,
                    "metadata": {"reason": "model_asked_follow_up"},
                }

            # Default: a normal answer
            return {
                "message": message,
                "follow_up": False,
                "fallback": False,
                "metadata": {"confidence": confidence},
            }

        except Exception as e:
            logger.exception("Exception while processing response")
            return self.error_handler.handle_exception(e, context={"raw_response": raw_response, "user_input": user_input})

    # Heuristics
    @staticmethod
    def _contains_follow_up_question(text: str) -> bool:
        # Simple heuristic: presence of a question sentence in response that appears addressed to the user
        # e.g. "Do you want...", "Would you like...", or any trailing question mark
        question_patterns = [r"\bdo you\b", r"\bwould you\b", r"\bcan you\b", r"\bwould you like\b"]
        lowered = text.lower()
        if '?' in text:
            return True
        for p in question_patterns:
            if re.search(p, lowered):
                return True
        return False

    @staticmethod
    def _is_incomplete_input(user_input: str) -> bool:
        """Check if user input appears too short or vague to process.

        Note: This should be used in conjunction with product matching checks,
        as product names alone (e.g., "serenicare") are valid complete queries.
        """
        if not user_input or not user_input.strip():
            return True
        # Very short inputs (1-2 tokens) likely need clarification
        tokens = user_input.strip().split()
        if len(tokens) <= 2:
            return True
        return False

    @staticmethod
    def _query_matches_product(user_input: str, products_matched: Optional[list]) -> bool:
        """True if we have matched products and the user query is that product name.

        Examples:
        - 'serenicare' matches ['Serenicare']
        - 'Personal accident' matches ['Personal Accident Insurance']
        - 'motor' matches ['Motor Private Insurance']
        """
        if not user_input or not products_matched:
            return False
        q = user_input.strip().lower()
        if not q:
            return False
        for name in products_matched:
            if not name:
                continue
            n = (name or "").strip().lower()
            if q == n or q in n or n in q:
                logger.debug("Query '%s' matches product '%s'", user_input, name)
                return True
        logger.debug("Query '%s' does not match any of %s", user_input, products_matched)
        return False
