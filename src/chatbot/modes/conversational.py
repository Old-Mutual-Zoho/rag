"""
Conversational mode - RAG-powered free-form chat
"""

from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


def _is_greeting(message: str) -> bool:
    m = (message or "").strip().lower()
    if not m:
        return False
    # Keep it strict so we don't mis-classify real questions.
    return m in {"hi", "hello", "hey", "hey!", "hello!", "hi!", "good morning", "good afternoon", "good evening"}


def _detect_section_intent(message: str) -> str | None:
    m = (message or "").lower()
    # Benefits
    if any(k in m for k in ["benefit", "benefits", "advantages", "what do i get", "what do you cover"]):
        return "show_benefits"
    # Coverage
    if any(k in m for k in ["coverage", "covered", "what is covered", "what's covered", "what is included", "included"]):
        return "show_coverage"
    # Exclusions
    if any(k in m for k in ["exclusion", "exclusions", "not covered", "what is not covered", "what isn't covered", "limitations"]):
        return "show_exclusions"
    # Eligibility
    if any(k in m for k in ["eligibility", "eligible", "qualify", "requirements", "who can apply", "who is it for"]):
        return "show_eligibility"
    # Pricing
    if any(k in m for k in ["premium", "price", "pricing", "cost", "how much"]):
        return "show_pricing"
    return None


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

        # Lazily import response processor to avoid circular imports at module load time
        try:
            from src.response_processor import ResponseProcessor

            self.response_processor = ResponseProcessor(state_manager=self.state_manager)
        except Exception:
            # Fallback: no response processor available
            self.response_processor = None

    async def process(self, message: str, session_id: str, user_id: str, form_data: Optional[Dict[str, Any]] = None) -> Dict:
        """Process message in conversational mode"""

        # Friendly greeting (avoid sending "hi" into RAG/LLM).
        if form_data is None and _is_greeting(message):
            return {
                "mode": "conversational",
                "response": (
                    "Hey! 👋 I’m MIA. How can I help today?\n"
                    "✨ You can ask about benefits, coverage, exclusions, or eligibility for a product.\n"
                    "For example: ‘benefits of Travel Sure Plus’ or ‘tell me about Serenicare’."
                ),
                "intent": "greeting",
                "confidence": 1.0,
            }

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

        # If the user is explicitly asking for a product section (benefits/coverage/etc),
        # resolve the product and answer via the product-guide path (filters by doc_id).
        if form_data is None:
            section_action = _detect_section_intent(message)
            if section_action:
                products = self.product_matcher.match_products(message, top_k=1)

                # Prefer explicit mention in message, else fall back to last product topic.
                session = self.state_manager.get_session(session_id) or {}
                ctx = dict(session.get("context") or {})

                picked = products[0][2] if products else None
                if picked:
                    ctx["product_topic"] = {
                        "digital_flow": _detect_digital_flow(message),
                        "name": picked.get("name"),
                        "doc_id": picked.get("product_id"),
                        "url": picked.get("url"),
                    }
                    self.state_manager.update_session(session_id, {"context": ctx})

                # If we still don't know which product, ask a single clarifying question.
                topic = (ctx.get("product_topic") or {}) if isinstance(ctx, dict) else {}
                if not topic.get("doc_id"):
                    return {
                        "mode": "conversational",
                        "response": (
                            "Sure 🙂 Which product do you mean?\n"
                            "Examples: ✈️ Travel Sure Plus, 🩹 Personal Accident, 🏥 Serenicare, 🚗 Motor Private."
                        ),
                        "intent": "clarify_product",
                        "confidence": 0.9,
                    }

                return await self._process_product_guide_action({"action": section_action}, session_id)

        # Detect intent
        intent = self._detect_intent(message)

        # Match relevant products
        products = self.product_matcher.match_products(message, top_k=3)

        # Build filters for RAG retrieval.
        # Key principle: default to ONE product when we're confident; otherwise
        # leave retrieval unfiltered so the model can ask a clarifying question.
        filters: Dict[str, Any] = {}
        if products:
            top_score = float(products[0][0] or 0.0)
            second_score = float(products[1][0] or 0.0) if len(products) > 1 else 0.0
            is_confident = (top_score >= 1.2) and (top_score >= second_score + 0.5)

            if intent == "compare":
                # Comparing products: allow multiple doc_ids.
                filters["products"] = [p[2]["product_id"] for p in products[:3]]
            elif is_confident:
                # Single-product intent: restrict to the best match.
                filters["products"] = [products[0][2]["product_id"]]
            else:
                # Not confident: avoid accidental wrong-product filtering.
                filters = {}

        # Retrieve relevant documents (top_k from RAG config when not specified)
        retrieval_results = await self.rag.retrieve(query=message, filters=filters or None)

        # Generate response
        response = await self.rag.generate(query=message, context_docs=retrieval_results, conversation_history=self._get_recent_history(session_id))

        # Use ResponseProcessor if available to normalize and handle follow-ups/fallbacks
        session = self.state_manager.get_session(session_id) or {}
        products_matched_names = [p[2]["name"] for p in products] if products else []
        if self.response_processor:
            processed = self.response_processor.process_response(
                raw_response=response.get("answer"),
                user_input=message,
                confidence=response.get("confidence", 0.0),
                conversation_state=session,
                session_id=session_id,
                products_matched=products_matched_names,
            )
            answer_text = processed.get("message")
            follow_up_flag = processed.get("follow_up", False)
        else:
            answer_text = response["answer"]
            follow_up_flag = False

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

        # If response processor already queued a follow-up, prefer that text over our generic follow_up_prompt
        if follow_up_flag:
            # If the processor flagged a follow-up, we assume it already queued it.
            # Keep the model-provided message as-is.
            pass
        elif follow_up_prompt:
            answer_text = f"{answer_text}\n\n{follow_up_prompt}" if answer_text else follow_up_prompt

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

        # Process generation through ResponseProcessor if available so follow-ups/fallbacks are handled consistently
        session = self.state_manager.get_session(session_id) or {}
        if self.response_processor:
            processed = self.response_processor.process_response(
                raw_response=gen.get("answer"),
                user_input=query,
                confidence=gen.get("confidence", 0.0),
                conversation_state=session,
                session_id=session_id,
            )
            gen_text = processed.get("message")
            follow_up_flag = processed.get("follow_up", False)
        else:
            gen_text = gen.get("answer")
            follow_up_flag = False

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

        response_text = gen_text
        if not follow_up_flag and follow_up:
            response_text = f"{gen_text}\n\n{follow_up}" if gen_text else follow_up

        return {
            "mode": "conversational",
            "response": response_text,
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
            "product_id": product.get("product_key") or product["product_id"],
            "doc_id": product.get("doc_id") or product.get("product_id"),
            "name": product["name"],
            "category": product.get("category_name", ""),
            "description": product.get("description", ""),
            "min_premium": product.get("min_premium"),
            "actions": [{"type": "learn_more", "label": "Learn More"}, {"type": "get_quote", "label": "Get a Quote"}],
        }
