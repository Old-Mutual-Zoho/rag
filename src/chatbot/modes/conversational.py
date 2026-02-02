"""
Conversational mode - RAG-powered free-form chat
"""

from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


def _detect_digital_flow(message: str) -> str | None:
    m = (message or "").lower()
    if any(k in m for k in ["personal accident", "pa cover", "accident insurance", "accident cover", "pa insurance"]):
        return "personal_accident"
    if any(k in m for k in ["serenicare"]):
        return "serenicare"
    if any(k in m for k in ["motor private", "car insurance", "vehicle insurance", "motor insurance"]):
        return "motor_private"
    if any(k in m for k in ["travel insurance", "travel sure", "travel cover", "travel policy"]):
        return "travel_insurance"
    return None


def _is_affirmative(message: str) -> bool:
    m = (message or "").strip().lower()
    return m in {"yes", "y", "yeah", "yep", "sure", "ok", "okay", "please", "go ahead", "go on"}


def _is_negative(message: str) -> bool:
    m = (message or "").strip().lower()
    return m in {"no", "n", "nope", "not now", "later", "maybe later"}


def _build_section_query(product_name: str, section: str) -> str:
    base = product_name or "this insurance product"
    if section == "show_benefits":
        return f"List the key benefits of {base}. Keep it clear and structured."
    if section == "show_eligibility":
        return f"Explain eligibility requirements for {base}. Include who it is for and common requirements."
    if section == "show_coverage":
        return f"Explain what is covered under {base}. Provide a clear coverage summary."
    if section == "show_exclusions":
        return f"Explain common exclusions and what is not covered for {base}."
    if section == "show_pricing":
        return f"Explain how pricing/premiums work for {base}. If exact prices are not available, explain the factors that affect cost."
    return f"Explain {base} insurance product, its benefits, coverage, and eligibility."


def _next_section_offer(action: str, *, is_digital: bool) -> tuple[str | None, str | None]:
    order = {
        "show_benefits": ("show_eligibility", "eligibility"),
        "show_eligibility": ("show_coverage", "coverage"),
        "show_coverage": ("show_exclusions", "exclusions"),
        "show_exclusions": ("show_pricing", "pricing"),
        "show_pricing": ("get_quote", "a quick quote") if is_digital else ("how_to_access", "how to access it"),
    }
    return order.get(action, (None, None))


class ConversationalMode:
    def __init__(self, rag_system, product_matcher, state_manager):
        self.rag = rag_system
        self.product_matcher = product_matcher
        self.state_manager = state_manager

    async def process(self, message: str, session_id: str, user_id: str, form_data: Optional[Dict[str, Any]] = None) -> Dict:
        """Process message in conversational mode"""

        # Backward-compatible: if the frontend still sends a product-guide action via form_data,
        # handle it, but we no longer *emit* buttons/actions as the primary UX.
        if form_data and isinstance(form_data, dict) and form_data.get("action"):
            return await self._process_product_guide_action(form_data, session_id)

        # If we previously offered to share a section (e.g., benefits) and the user replies "yes",
        # convert that into the corresponding section answer.
        session = self.state_manager.get_session(session_id) or {}
        ctx = dict(session.get("context") or {})
        pending_offer = ctx.get("pending_section_offer")
        if pending_offer:
            if _is_affirmative(message):
                ctx.pop("pending_section_offer", None)
                self.state_manager.update_session(session_id, {"context": ctx})
                return await self._process_product_guide_action({"action": str(pending_offer)}, session_id)
            if _is_negative(message):
                ctx.pop("pending_section_offer", None)
                self.state_manager.update_session(session_id, {"context": ctx})
            elif (message or "").strip():
                # User asked something else; clear the pending offer to avoid accidental triggers.
                ctx.pop("pending_section_offer", None)
                self.state_manager.update_session(session_id, {"context": ctx})

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

        # Determine product topic for follow-up guidance.
        digital_flow = _detect_digital_flow(message)
        top_product = products[0][2] if products else None

        if digital_flow or top_product:
            topic_name = None
            topic_url = None
            topic_doc_id = None

            if top_product:
                topic_name = top_product.get("name")
                topic_url = top_product.get("url")
                topic_doc_id = top_product.get("product_id")

            # Persist topic in session context (so buttons can work).
            session = self.state_manager.get_session(session_id) or {}
            ctx = dict(session.get("context") or {})
            ctx["product_topic"] = {
                "digital_flow": digital_flow,
                "name": topic_name,
                "doc_id": topic_doc_id,
                "url": topic_url,
            }
            self.state_manager.update_session(session_id, {"context": ctx})

        # Append a natural follow-up prompt when the user is learning about a product.
        follow_up_prompt = None
        if intent in ("learn", "general", "compare", "discover") and (digital_flow or top_product):
            # Offer benefits as the next step, but keep the UX conversational.
            follow_up_prompt = (
                "Do you have any more questions, or should I share the benefits? "
                "Reply 'yes' for benefits, or type your next question."
            )

            # Store what a simple "yes" should do next.
            session = self.state_manager.get_session(session_id) or {}
            ctx = dict(session.get("context") or {})
            ctx["pending_section_offer"] = "show_benefits"
            self.state_manager.update_session(session_id, {"context": ctx})

        # Determine if we should suggest guided mode
        suggested_action = None
        if intent in ["quote", "buy", "apply", "purchase"]:
            digital_flow = _detect_digital_flow(message)

            if digital_flow:
                suggested_action = {
                    "type": "switch_to_guided",
                    "message": "I can get you a quotation now.",
                    "flow": "journey",
                    "initial_data": {"product_flow": digital_flow},
                    "buttons": [
                        {"label": "Get quotation", "action": "get_quotation"},
                        {"label": "Not now", "action": "continue_chat"},
                    ],
                }
            elif products:
                top = products[0][2]
                suggested_action = {
                    "type": "access_info",
                    "message": (
                        f"{top.get('name', 'This product')} is not available as a digital buy/quote journey in this chatbot. "
                        "To access it, please visit an Old Mutual branch/agent or contact customer support."
                        + (f"\n\nMore details: {top.get('url')}" if top.get("url") else "")
                    ),
                }
            else:
                suggested_action = {
                    "type": "switch_to_guided",
                    "message": "I can guide you through our available digital products to get a quote.",
                    "flow": "journey",
                    "buttons": [
                        {"label": "Start", "action": "start_guided"},
                        {"label": "Not now", "action": "continue_chat"},
                    ],
                }
        elif intent == "discover" and products:
            suggested_action = {
                "type": "show_product_cards",
                "message": "Here are some products that might interest you:",
                "products": [self._generate_product_card(p[2]) for p in products],
            }

        # No product-guide buttons by default; users can reply in free text.

        answer_text = response["answer"]
        if follow_up_prompt:
            answer_text = f"{answer_text}\n\n{follow_up_prompt}"

        return {
            "mode": "conversational",
            "response": answer_text,
            "sources": response.get("sources", []),
            "products_matched": [p[2]["name"] for p in products],
            "intent": intent,
            "suggested_action": suggested_action,
            "confidence": response.get("confidence", 0.5),
        }

    async def _process_product_guide_action(self, form_data: Dict[str, Any], session_id: str) -> Dict:
        action = str(form_data.get("action") or "").strip()

        session = self.state_manager.get_session(session_id) or {}
        ctx = session.get("context") or {}
        topic = (ctx.get("product_topic") or {}) if isinstance(ctx, dict) else {}

        digital_flow = topic.get("digital_flow")
        product_name = topic.get("name") or (digital_flow.replace("_", " ").title() if digital_flow else None)
        doc_id = topic.get("doc_id")
        url = topic.get("url")

        # Quote button: frontend should start guided journey (digital only).
        # The router handles action=get_quotation and will immediately return the first product form/cards.
        if action == "get_quote" and digital_flow:
            return {
                "mode": "conversational",
                "response": "Sure — click 'Get quotation' to begin.",
                "suggested_action": {
                    "type": "switch_to_guided",
                    "flow": "journey",
                    "initial_data": {"product_flow": digital_flow},
                    "buttons": [{"label": "Get quotation", "action": "get_quotation"}],
                },
            }

        if action == "how_to_access":
            msg = "This product is not available as a digital buy/quote journey in this chatbot. "
            msg += "To access it, please visit an Old Mutual branch/agent or contact customer support."
            if url:
                msg += f"\n\nMore details: {url}"
            return {
                "mode": "conversational",
                "response": msg,
            }

        query = _build_section_query(product_name or "", action)
        filters = {"products": [doc_id]} if doc_id else None
        hits = await self.rag.retrieve(query=query, filters=filters)
        gen = await self.rag.generate(query=query, context_docs=hits, conversation_history=self._get_recent_history(session_id))

        next_action, next_label = _next_section_offer(action, is_digital=bool(digital_flow))

        follow_up = "Do you have any more questions?"
        if next_action and next_label:
            follow_up = (
                f"Do you have any more questions, or should I share the {next_label}? "
                f"Reply 'yes' for {next_label}, or type your next question."
            )

            # Store what a simple "yes" should do next.
            session = self.state_manager.get_session(session_id) or {}
            ctx = dict(session.get("context") or {})
            ctx["pending_section_offer"] = next_action
            self.state_manager.update_session(session_id, {"context": ctx})

        return {
            "mode": "conversational",
            "response": f"{gen['answer']}\n\n{follow_up}",
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
