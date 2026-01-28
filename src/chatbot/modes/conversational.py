"""
Conversational mode - RAG-powered free-form chat
"""

from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class ConversationalMode:
    def __init__(self, rag_system, product_matcher, state_manager):
        self.rag = rag_system
        self.product_matcher = product_matcher
        self.state_manager = state_manager

    async def process(self, message: str, session_id: str, user_id: str) -> Dict:
        """Process message in conversational mode"""

        # Detect intent
        intent = self._detect_intent(message)

        # Match relevant products
        products = self.product_matcher.match_products(message, top_k=3)

        # Build filters for RAG retrieval
        filters = {}
        if products:
            filters["products"] = [p[2]["product_id"] for p in products]

        # Retrieve relevant documents (top_k from RAG config when not specified)
        retrieval_results = await self.rag.retrieve(query=message, filters=filters)

        # Generate response
        response = await self.rag.generate(query=message, context_docs=retrieval_results, conversation_history=self._get_recent_history(session_id))

        # Determine if we should suggest guided mode
        suggested_action = None
        if intent in ["quote", "buy", "apply", "purchase"]:
            suggested_action = {
                "type": "switch_to_guided",
                "message": "💡 Would you like me to help you get a quote?",
                "flow": "quotation",
                "buttons": [{"label": "Yes, get a quote", "action": "start_guided_quotation"}, {"label": "No, just browsing", "action": "continue_chat"}],
            }
        elif intent == "discover" and products:
            suggested_action = {
                "type": "show_product_cards",
                "message": "Here are some products that might interest you:",
                "products": [self._generate_product_card(p[2]) for p in products],
            }

        return {
            "mode": "conversational",
            "response": response["answer"],
            "sources": response.get("sources", []),
            "products_matched": [p[2]["name"] for p in products],
            "intent": intent,
            "suggested_action": suggested_action,
            "confidence": response.get("confidence", 0.5),
        }

    def _detect_intent(self, message: str) -> str:
        """Detect user intent from message"""
        message_lower = message.lower()

        # Quote/Purchase intents
        if any(word in message_lower for word in ["quote", "how much", "price", "cost", "premium"]):
            return "quote"

        if any(word in message_lower for word in ["buy", "purchase", "apply", "get insurance"]):
            return "buy"

        # Discovery intents
        if any(word in message_lower for word in ["what is", "tell me about", "explain", "how does"]):
            return "learn"

        if any(word in message_lower for word in ["compare", "difference", "vs", "versus"]):
            return "compare"

        if any(word in message_lower for word in ["need", "looking for", "want", "recommend"]):
            return "discover"

        # Claims/Support
        if any(word in message_lower for word in ["claim", "file", "submit"]):
            return "claim"

        # Default
        return "general"

    def _get_recent_history(self, session_id: str, limit: int = 5) -> List[Dict]:
        """Get recent conversation history"""
        session = self.state_manager.get_session(session_id)
        if not session:
            return []

        # Get from PostgreSQL
        messages = self.state_manager.db.get_conversation_history(session["conversation_id"], limit=limit)

        return [{"role": msg.role, "content": msg.content} for msg in reversed(messages)]

    def _generate_product_card(self, product: Dict) -> Dict:
        """Generate product card data"""
        return {
            "product_id": product["product_id"],
            "name": product["name"],
            "category": product.get("category_name", ""),
            "description": product.get("description", ""),
            "min_premium": product.get("min_premium"),
            "actions": [{"type": "learn_more", "label": "Learn More"}, {"type": "get_quote", "label": "Get a Quote"}],
        }
