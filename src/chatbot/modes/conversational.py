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
    # Handle common missing-space variants like "goodmorning".
    m = (
        m.replace("goodmorning", "good morning")
        .replace("goodafternoon", "good afternoon")
        .replace("goodevening", "good evening")
    )
    if m in {
        "hi",
        "hello",
        "hey",
        "hey!",
        "hello!",
        "hi!",
        "good morning",
        "good afternoon",
        "good evening",
        "gm",
        "gdm",
        "gud morning",
        "gud evening",
        "morning",
        "evening",
        "hiya",
        "yo",
        "sup",
        "heyyo",
        "whatsapp",
    }:
        return True
    # Allow simple greetings inside a longer sentence.
    return any(
        g in m
        for g in [
            "hi ",
            "hello ",
            "hey ",
            "hi there",
            "hello there",
            "hey there",
            "good morning",
            "good afternoon",
            "good evening",
            "gm ",
            "gud morning",
            "gud evening",
            "morning ",
            "evening ",
            "yo ",
            "sup ",
            "whatsapp",
        ]
    )


def _detect_section_intent(message: str) -> str | None:
    m = (message or "").lower()
    # Benefits
    if any(
        k in m
        for k in [
            "benefit",
            "benefits",
            "advantages",
            "value",
            "perks",
            "what do i get",
            "what do you cover",
            "why should i",
            "convince me",
            "what's in it for me",
            "what do i gain",
        ]
    ):
        return "show_benefits"
    # Coverage
    if any(
        k in m
        for k in [
            "coverage",
            "covered",
            "what is covered",
            "what's covered",
            "what is included",
            "included",
            "does it cover",
            "am i covered",
            "if i",
            "in case of",
            "when it happens",
        ]
    ):
        return "show_coverage"
    # Exclusions
    if any(
        k in m
        for k in [
            "exclusion",
            "exclusions",
            "not covered",
            "what is not covered",
            "what isn't covered",
            "limitations",
            "fine print",
            "what you don't cover",
            "what you wont cover",
            "won't cover",
            "doesn't cover",
        ]
    ):
        return "show_exclusions"
    # Eligibility
    if any(
        k in m
        for k in [
            "eligibility",
            "eligible",
            "qualify",
            "requirements",
            "who can apply",
            "who is it for",
            "is it for me",
            "can i apply",
            "age limit",
            "age requirement",
            "employment status",
            "health status",
        ]
    ):
        return "show_eligibility"
    # Pricing
    if any(
        k in m
        for k in [
            "premium",
            "price",
            "pricing",
            "cost",
            "how much",
            "afford",
            "budget",
            "payment",
            "installment",
            "monthly",
            "per month",
            "per year",
            "annually",
        ]
    ):
        return "show_pricing"
    return None


def _detect_digital_flow(message: str) -> str | None:
    m = (message or "").lower()
    if any(k in m for k in ["personal accident", "pa cover", "accident insurance", "accident cover", "pa insurance"]):
        return "personal_accident"
    if any(k in m for k in ["serenicare"]):
        return "serenicare"
    if any(
        k in m
        for k in [
            "motor private",
            "car insurance",
            "vehicle insurance",
            "motor insurance",
            "car cover",
            "vehicle cover",
            "auto insurance",
        ]
    ):
        return "motor_private"
    if any(
        k in m
        for k in [
            "travel insurance",
            "travel sure",
            "travel cover",
            "travel policy",
            "trip cover",
            "trip insurance",
            "flight insurance",
            "going abroad",
        ]
    ):
        return "travel_insurance"
    return None


def _is_domain_related(message: str) -> bool:
    m = (message or "").lower()
    if not m:
        return False
    domain_keywords = [
        "old mutual",
        "insurance",
        "policy",
        "cover",
        "coverage",
        "claim",
        "premium",
        "quote",
        "buy",
        "apply",
        "benefit",
        "exclusion",
        "eligibility",
        "motor",
        "travel",
        "life",
        "health",
        "medical",
        "investment",
        "investments",
        "unit trust",
        "savings",
        "serenicare",
        "personal accident",
        "pa cover",
        "insured",
        "policyholder",
        "sum assured",
        "deductible",
        "copay",
        "claim form",
        "accident",
        "hospital",
        "medical bill",
        "treatment",
        "risk",
        "protection",
        "coverage limit",
    ]
    return any(k in m for k in domain_keywords)


def _is_affirmative(message: str) -> bool:
    m = (message or "").strip().lower()
    return m in {
        "yes",
        "y",
        "yeah",
        "yep",
        "sure",
        "ok",
        "okay",
        "please",
        "go ahead",
        "go on",
        "alright",
        "sounds good",
        "do it",
        "👍",
        "✅",
    }


def _is_negative(message: str) -> bool:
    m = (message or "").strip().lower()
    return m in {"no", "n", "nope", "not now", "later", "maybe later", "not today", "no thanks", "nah", "pass"}


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

        # Optional LLM-based intent classifier & small-talk responder.
        try:
            from src.chatbot.intent_classifier import IntentClassifier, SmallTalkResponder

            self.intent_classifier = IntentClassifier()
            self.small_talk_responder = SmallTalkResponder()
        except Exception:
            self.intent_classifier = None
            self.small_talk_responder = None

        # Lazily import response processor to avoid circular imports at module load time
        try:
            from src.response_processor import ResponseProcessor

            self.response_processor = ResponseProcessor(state_manager=self.state_manager)
        except Exception:
            # Fallback: no response processor available
            self.response_processor = None

    async def process(self, message: str, session_id: str, user_id: str, form_data: Optional[Dict[str, Any]] = None) -> Dict:
        """Process message in conversational mode"""

        # Normalize empty form_data to None so gating logic works as intended.
        if not form_data:
            form_data = None

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

        # NO_RETRIEVAL intents (greetings, small talk, thanks, goodbyes).
        # First, apply a very small heuristic gate for obvious cases.
        if form_data is None:
            no_ret_kind = self._detect_no_retrieval_intent(message)
            if no_ret_kind:
                # Obvious small-talk/greeting/thanks/goodbye: skip classifier and RAG.
                answer_text = self._build_no_retrieval_reply(no_ret_kind)
                return {
                    "mode": "conversational",
                    "response": answer_text,
                    "sources": [],
                    "products_matched": [],
                    "intent": no_ret_kind.lower(),
                    "intent_type": "NO_RETRIEVAL",
                    "suggested_action": None,
                    "confidence": 1.0,
                }

            # For more ambiguous inputs, fall back to LLM-based intent classification
            # when available. This further separates small talk vs informational queries.
            if self.intent_classifier is not None:
                try:
                    llm_intent = await self.intent_classifier.classify(message)
                except Exception:
                    llm_intent = None

                if llm_intent and llm_intent.intent_type == "NO_RETRIEVAL":
                    # Treat generic OTHER as off-topic to avoid a misleading overview.
                    label = llm_intent.label
                    if label == "OTHER":
                        label = "OFF_TOPIC"
                    # Use deterministic replies for GREETING to avoid partial outputs.
                    if label == "GREETING":
                        answer_text = self._build_no_retrieval_reply(label)
                    # Use LLM responder only for safe small-talk intents.
                    elif label in {"SMALL_TALK", "THANKS", "GOODBYE"} and self.small_talk_responder is not None:
                        answer_text = await self.small_talk_responder.respond(message, label)
                    else:
                        answer_text = self._build_no_retrieval_reply(label)
                    return {
                        "mode": "conversational",
                        "response": answer_text,
                        "sources": [],
                        "products_matched": [],
                        "intent": label.lower(),
                        "intent_type": "NO_RETRIEVAL",
                        "suggested_action": None,
                        "confidence": 1.0,
                    }

        # Detect coarse intent (quote/buy/learn/etc.)
        intent = self._detect_intent(message)

        # Match relevant products
        products = self.product_matcher.match_products(message, top_k=3)

        # If it's not about the domain and no products match, treat as off-topic.
        if not _is_domain_related(message) and not products:
            answer_text = self._build_no_retrieval_reply("OFF_TOPIC")
            return {
                "mode": "conversational",
                "response": answer_text,
                "sources": [],
                "products_matched": [],
                "intent": "off_topic",
                "intent_type": "NO_RETRIEVAL",
                "suggested_action": None,
                "confidence": 1.0,
            }

        # Classify high-level semantic intent before retrieval (OVERVIEW, BUSINESS_UNIT, PRODUCT_LIST, etc.)
        session_for_intent = self.state_manager.get_session(session_id) or {}
        semantic_intent = self._classify_intent(
            message=message,
            coarse_intent=intent,
            products=products,
            conversation_state=session_for_intent,
        )

        # For high-level OVERVIEW questions (e.g. "What does Old Mutual offer?")
        # return a structured, category-based summary built directly from the
        # product index instead of deep-diving into a couple of random products.
        if semantic_intent == "OVERVIEW" and not products:
            overview_text, _overview_sources = self._build_overview_summary()
            return {
                "mode": "conversational",
                "response": overview_text,
                "sources": [],
                "products_matched": [],
                "intent": intent,
                "intent_type": semantic_intent,
                "suggested_action": None,
                "confidence": 0.7,
            }

        # Build filters for RAG retrieval.
        # Key principle: default to ONE product when we're confident; otherwise
        # leave retrieval unfiltered so the model can ask a clarifying question.
        filters: Dict[str, Any] = {}
        if products:
            top_score = float(products[0][0] or 0.0)
            second_score = float(products[1][0] or 0.0) if len(products) > 1 else 0.0
            is_confident = (top_score >= 1.2) and (top_score >= second_score + 0.5)

            if intent == "compare" or semantic_intent == "COMPARISON":
                # Comparing products: allow multiple doc_ids.
                filters["products"] = [p[2]["product_id"] for p in products[:3]]
            elif is_confident:
                # Single-product intent: restrict to the best match.
                filters["products"] = [products[0][2]["product_id"]]
            else:
                # Not confident: avoid accidental wrong-product filtering.
                filters = {}
        elif semantic_intent == "PRODUCT_LIST":
            # "What products do you have under X?" – focus on product documents.
            filters["type"] = "product"
        elif semantic_intent == "BUSINESS_UNIT":
            # Questions like "What does Old Mutual Investments do?"
            # Prefer info/about-us style pages over individual products.
            filters["type"] = "info_page"

        # Retrieve relevant documents (hybrid BM25 + vector via APIRAGAdapter).
        # Tune depth per high-level intent:
        # - OVERVIEW/BUSINESS_UNIT: fetch more context so the LLM can summarise.
        # - PRODUCT_DETAIL: tighter, product-specific chunks only.
        # - default: use config top_k.
        top_k: Optional[int]
        if semantic_intent in {"OVERVIEW", "BUSINESS_UNIT"}:
            top_k = 15
        elif semantic_intent == "PRODUCT_DETAIL":
            top_k = 5
        else:
            top_k = None

        retrieval_results = await self.rag.retrieve(query=message, filters=filters or None, top_k=top_k)

        # Defensive gate: for OVERVIEW intents, ensure we don't answer using only
        # product-level documents. If all hits are product chunks, enrich with
        # high-level info pages (about-us, business units).
        if semantic_intent == "OVERVIEW":
            has_non_product = any(
                (h.get("payload") or {}).get("type") and (h.get("payload") or {}).get("type") != "product"
                for h in retrieval_results
            )
            if not has_non_product:
                extra_info_hits = await self.rag.retrieve(query=message, filters={"type": "info_page"}, top_k=5)
                if extra_info_hits:
                    seen_ids = {h["id"] for h in retrieval_results}
                    for h in extra_info_hits:
                        if h["id"] not in seen_ids:
                            retrieval_results.append(h)
                            seen_ids.add(h["id"])

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
            "intent_type": semantic_intent,
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
        """Detect coarse user intent from message (quote/buy/learn/compare/discover/claim/general)."""
        message_lower = message.lower()

        # Quote/Purchase intents
        if any(
            word in message_lower
            for word in [
                "quote",
                "how much",
                "price",
                "cost",
                "premium",
                "afford",
                "budget",
                "payment",
                "installment",
                "monthly",
            ]
        ):
            return "quote"

        if any(word in message_lower for word in ["buy", "purchase", "apply", "get insurance"]):
            return "buy"

        # Discovery / learning intents
        if any(word in message_lower for word in ["what is", "tell me about", "explain", "how does", "guide me", "learn about"]):
            return "learn"

        if any(word in message_lower for word in ["compare", "difference", "vs", "versus", "better than", "which is better", "which one is better"]):
            return "compare"

        if any(
            word in message_lower
            for word in [
                "need",
                "looking for",
                "want",
                "recommend",
                "suggest",
                "advise",
                "help me choose",
            ]
        ):
            return "discover"

        # Claims/Support
        if any(
            word in message_lower
            for word in ["claim", "file", "submit", "accident", "incident", "loss", "damage", "hospital", "urgent"]
        ):
            return "claim"

        # Default
        return "general"

    def _detect_no_retrieval_intent(self, message: str) -> Optional[str]:
        """
        Detect intents that should never trigger retrieval (NO_RETRIEVAL):
        GREETING, SMALL_TALK, THANKS, GOODBYE.
        """
        m = (message or "").strip().lower()
        if not m:
            return None

        # Greetings
        if _is_greeting(m) and any(k in m for k in ["help", "assist", "support"]):
            return "HELP"
        if _is_greeting(m):
            return "GREETING"

        # Thanks / appreciation
        thanks_phrases = {
            "thanks",
            "thank you",
            "thank you!",
            "thanks!",
            "thx",
            "thank u",
            "thanks a lot",
            "much appreciated",
            "appreciate it",
            "cheers",
            "ty",
            "thnx",
            "🙏",
            "👍",
        }
        if m in thanks_phrases:
            return "THANKS"

        # Goodbyes
        goodbye_phrases = {
            "bye",
            "goodbye",
            "bye!",
            "goodbye!",
            "see you",
            "see you later",
            "see ya",
            "cya",
            "catch you later",
            "talk later",
            "i'm done",
            "that is all",
            "that's all",
        }
        if m in goodbye_phrases:
            return "GOODBYE"

        # Simple small talk
        small_talk_phrases = {
            "how are you",
            "how are you?",
            "how are u",
            "how are u?",
            "how's it going",
            "how's it going?",
            "hi",
            "whatsapp",
            "hello",
            "what's up",
            "whats up",
            "wassup",
            "are you there",
            "you there",
            "you around",
            "available?",
            "busy?",
        }
        if m in small_talk_phrases:
            return "SMALL_TALK"


        # Off-topic personal/identity questions (avoid retrieval)
        if any(
            k in m
            for k in [
                "do you know",
                "who is",
                "who's",
                "who are",
                "do you know about",
                "what's your name",
                "what is your name",
                "where are you",
                "are you real",
            ]
        ):
            if "old mutual" not in m and "policy" not in m and "insurance" not in m:
                return "OFF_TOPIC"

        # Personal feelings without a clear product/insurance context
        if any(k in m for k in ["i feel", "i'm feeling", "i am feeling", "i feel like", "i feel so", "i'm sad", "i am sad"]):
            if not any(k in m for k in ["insurance", "policy", "claim", "quote", "premium", "cover", "coverage"]):
                return "OFF_TOPIC"

        return None

    def _build_no_retrieval_reply(self, kind: str) -> str:
        """
        Build a conversational reply for NO_RETRIEVAL intents without hitting RAG.
        """
        kind = (kind or "").upper()

        if kind == "GREETING":
            return (
                "Hey! I’m MIA, your Old Mutual assistant.\n"
                "You can ask me about our products, benefits, coverage, or how to get a quote."
            )
        if kind == "THANKS":
            return "You’re welcome! If you have any more questions about Old Mutual products or services, I’m here to help."
        if kind == "GOODBYE":
            return "You’re welcome. Feel free to come back any time you need help with Old Mutual products or services."
        if kind == "SMALL_TALK":
            return "I’m doing well, thank you for asking. How can I help you with Old Mutual products or services today?"
        if kind == "HELP":
            return (
                "Sure — what do you need help with? You can ask about a product, coverage, claims, or getting a quote."
            )
        if kind == "OFF_TOPIC":
            return (
                "I’m here to help with Old Mutual products and services. "
                "If you have a question about insurance, savings, or claims, I can help with that."
            )

        # Fallback – should rarely be hit.
        return "I’m here to help with Old Mutual products and services. What would you like to know?"

    def _classify_intent(
        self,
        *,
        message: str,
        coarse_intent: str,
        products: List[Any],
        conversation_state: Dict[str, Any],
    ) -> str:
        """
        High-level semantic intent classifier used *before* retrieval.

        Intent types:
        - OVERVIEW: "What does Old Mutual offer?"
        - BUSINESS_UNIT: "What does Old Mutual Investments do?"
        - PRODUCT_LIST: "What products do you have under Life Insurance?"
        - PRODUCT_DETAIL: "Tell me about Old Mutual FlexiCover"
        - COMPARISON: "Compare Old Mutual vs Sanlam"
        - FOLLOW_UP: short, contextual questions like "What about investments?"
        """
        m = (message or "").strip().lower()
        if not m:
            return "FOLLOW_UP"

        ctx = conversation_state.get("context") or {}

        # Explicit comparison cues
        if any(k in m for k in ["compare", "difference between", " vs ", " versus "]) or coarse_intent == "compare":
            return "COMPARISON"

        # Company-/group-level overview questions
        if "old mutual" in m:
            if any(k in m for k in ["investments", "financial services", "asset management", "life assurance"]):
                return "BUSINESS_UNIT"
            if any(
                k in m
                for k in [
                    "what do you offer",
                    "what do you have to offer",
                    "what does old mutual offer",
                    "what does old mutual have to offer",
                    "what products do you have",
                    "what services do you have",
                    "what products do you offer",
                    "what services do you offer",
                    "what do you do",
                    "about you",
                    "about old mutual",
                ]
            ):
                return "OVERVIEW"

        # Product list questions: asking for a menu of options under a category
        if any(
            k in m
            for k in [
                "products do you have under",
                "plans do you have under",
                "products under",
                "plans under",
                "options under",
            ]
        ):
            return "PRODUCT_LIST"
        if any(
            k in m
            for k in [
                "what products do you have",
                "what plans do you have",
                "what options do you have",
            ]
        ) and any(
            cat in m
            for cat in [
                "life insurance",
                "life cover",
                "health insurance",
                "medical insurance",
                "motor insurance",
                "car insurance",
                "travel insurance",
                "savings",
                "investment",
                "investments",
            ]
        ):
            return "PRODUCT_LIST"

        # Product detail: strong match to a specific product name
        if products:
            top_score = float(products[0][0] or 0.0)
            if top_score >= 1.2 and coarse_intent in {"learn", "discover", "general"}:
                return "PRODUCT_DETAIL"

        # Follow-up style: short queries that rely on prior context
        tokens = m.split()
        if len(tokens) <= 4 and any(
            phrase in m for phrase in ["what about", "how about", "and ", "more about", "tell me more"]
        ):
            return "FOLLOW_UP"
        if len(tokens) <= 2 and ctx:
            # Single-word/very short follow-ups like "investments?" or "motor?"
            return "FOLLOW_UP"

        # Business-unit style without explicit "Old Mutual" but clearly about a function
        if any(
            k in m
            for k in [
                "investment arm",
                "investment business",
                "financial services arm",
                "unit trust",
                "unit trusts",
                "collective investment",
                "collective investment scheme",
                "mutual fund",
                "mutual funds",
            ]
        ):
            return "BUSINESS_UNIT"

        # Fallbacks based on coarse intent and presence of "old mutual"
        if "old mutual" in m and coarse_intent in {"learn", "discover", "general"}:
            return "OVERVIEW"

        if coarse_intent == "discover":
            return "OVERVIEW"

        # Very short, low-information inputs (e.g. "hello", "hi") should never be
        # treated as OVERVIEW. Treat them as FOLLOW_UP so that they can be gated
        # by no-retrieval logic upstream.
        if len(tokens) <= 2:
            return "FOLLOW_UP"

        return "FOLLOW_UP" if ctx else "OVERVIEW"

    def _build_overview_summary(self) -> tuple[str, List[Dict[str, Any]]]:
        """
        Build a high-level overview answer from the product index, grouped by category.

        This is used for OVERVIEW intent such as "What does Old Mutual offer?"
        so that the user sees the breadth of offerings (by business line) instead
        of a deep dive into just one or two products.
        """
        # Collect products by top-level category name (e.g. "personal", "business")
        by_category: Dict[str, List[Dict[str, Any]]] = {}
        for p in self.product_matcher.product_index.values():
            cat = (p.get("category_name") or "Other").strip()
            if not cat:
                cat = "Other"
            by_category.setdefault(cat, []).append(p)

        # Build human-readable bullets with a few flagship products per category
        lines: List[str] = []
        lines.append("Here’s an overview of what Old Mutual Uganda offers:")

        for cat, items in sorted(by_category.items()):
            # Sort products by name and pick a small sample so the list stays concise.
            items_sorted = sorted(items, key=lambda x: (x.get("name") or "").lower())
            sample = items_sorted[:3]
            names = [i.get("name") for i in sample if i.get("name")]
            if not names:
                continue

            more_suffix = " and more" if len(items_sorted) > len(sample) else ""
            lines.append(f"- **{cat}**: {', '.join(names)}{more_suffix}.")

        if len(lines) == 1:
            # No products indexed for some reason – fall back to a generic message.
            lines.append(
                "- **Savings & investments**, **life insurance**, **health cover**, and **general insurance** products tailored to different needs."
            )

        lines.append(
            "If you tell me what you're most interested in (for example life insurance, health, motor, or savings & investments), I can explain those in more detail."
        )

        # Second return value kept for backward-compatibility but is unused
        # by the conversational pipeline (no retrieval → no sources).
        return "\n".join(lines), []

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
