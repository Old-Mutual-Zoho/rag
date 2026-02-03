"""
Answer generation utilities (LLM) for the RAG pipeline - Ultra Natural Version.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List
import google.generativeai as genai
from google.api_core import exceptions

logger = logging.getLogger(__name__)


def _intent_from_question(question: str) -> str:
    q = (question or "").strip().lower()
    if not q:
        return "general"
    if q in {"hi", "hello", "hey", "hi!", "hello!", "hey!"}:
        return "greeting"
    if re.search(r"\b(benefit|benefits|advantages)\b", q):
        return "benefits"
    if re.search(r"\b(exclusion|exclusions|not covered|limitations)\b", q):
        return "exclusions"
    if re.search(r"\b(cover|coverage|covered|included|what does it cover)\b", q):
        return "coverage"
    if re.search(r"\b(eligible|eligibility|qualify|requirements|who is it for)\b", q):
        return "eligibility"
    if re.search(r"\b(premium|price|pricing|cost|how much)\b", q):
        return "pricing"
    if re.search(r"\b(quote|quotation)\b", q):
        return "quote"
    return "general"


def _style_block(intent: str) -> str:
    """Return intent-aware formatting rules and a small template.

    We intentionally keep this as plain text (no markdown headings) to keep chat UX natural.
    """
    common = """
Style rules (Meta-AI-like):
- Keep it warm and conversational, like a helpful assistant in WhatsApp.
- Use emojis naturally (not every line). Prefer 1–2 emojis per section.
- Keep it short: aim for 3–10 lines.
- If listing items, use emoji bullets like: ✅, ✨, 🧾, 🛡️, 🚫
- Never say: "Based on the context provided".
- Stay grounded in Available info. If unsure/missing, ask ONE short clarifying question.
- Don’t invent prices, benefits, or exclusions that aren’t in Available info.
""".strip()

    templates: dict[str, str] = {
        "greeting": """
Output template:
Hey! 👋 I’m MIA from Old Mutual Uganda.
What can I help you with today — benefits, coverage, exclusions, eligibility, or getting a quote?
""".strip(),
        "benefits": """
Output template:
Sure! Here are the key benefits 👇
✅ Benefit 1
✅ Benefit 2
✅ Benefit 3

Want me to share coverage or exclusions next?
""".strip(),
        "coverage": """
Output template:
Here’s what’s typically covered 👇
🛡️ Coverage item 1
🛡️ Coverage item 2
🛡️ Coverage item 3

Want exclusions or eligibility next?
""".strip(),
        "exclusions": """
Output template:
Good question — common exclusions include 👇
🚫 Exclusion 1
🚫 Exclusion 2
🚫 Exclusion 3

Want me to also share what IS covered?
""".strip(),
        "eligibility": """
Output template:
Here’s who it’s usually for 👇
🧾 Requirement / eligibility point 1
🧾 Requirement / eligibility point 2
🧾 Requirement / eligibility point 3

Want benefits or exclusions next?
""".strip(),
        "pricing": """
Output template:
Pricing depends on a few things 👇
💰 Factor 1
💰 Factor 2
💰 Factor 3

If you tell me the product + a few details, I can guide you to a quote.
""".strip(),
        "quote": """
Output template:
Absolutely — I can help you get a quote ✅
Which product are you quoting for (Travel Sure Plus, Personal Accident, Serenicare, Motor Private)?
""".strip(),
        "general": """
Output template:
Give a direct answer first (1–3 lines).
Then add 3–5 emoji bullets if it helps clarity.
End with ONE friendly follow-up question.
""".strip(),
    }

    return f"{common}\n\n{templates.get(intent, templates['general'])}"


def build_context(hits: List[Dict[str, Any]], *, max_chars: int = 10000) -> str:
    """
    Build a compact context string from retrieved Qdrant hits.
    """
    parts: list[str] = []
    used = 0
    for i, h in enumerate(hits, start=1):
        p = h.get("payload") or {}
        title = p.get("title") or ""
        url = p.get("url") or ""
        heading = p.get("section_heading") or ""
        text = (p.get("text") or "").strip()
        block = f"[{i}] {title}\n{url}\n{heading}\n{text}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts).strip()


def generate_with_gemini(
    *,
    question: str,
    hits: List[Dict[str, Any]],
    model: str,
    api_key_env: str = "GEMINI_API_KEY",
) -> str:
    """
    Generate a natural, human-like answer using Gemini.
    Args:
        question: User's question
        hits: Retrieved context chunks from Qdrant
        model: Gemini model name (e.g., 'gemini-1.5-flash')
        api_key_env: Environment variable name for API key

    Returns:
        Generated answer text or error message
    """
    key = os.environ.get(api_key_env)
    if not key:
        raise RuntimeError(f"{api_key_env} is not set")

    genai.configure(api_key=key)
    context = build_context(hits)

    intent = _intent_from_question(question)
    style = _style_block(intent)

    # Intent-aware conversational prompt (Meta-AI-like).
    prompt = f"""You're MIA, a friendly Old Mutual Uganda assistant.

Question: {question}

Available info:
{context}

{style}

Extra grounding rules:
- Only use details that appear in Available info.
- If Available info is empty/irrelevant, ask a single clarifying question.

Your response:"""

    # Initialize model
    m = genai.GenerativeModel(model)

    # Generation with retry logic
    try:
        resp = m.generate_content(prompt)
        return (getattr(resp, "text", None) or "").strip()

    except exceptions.ResourceExhausted as e:
        first_err = str(e).strip()
        logger.warning("Gemini ResourceExhausted: %s", first_err)

        time.sleep(5)
        try:
            resp = m.generate_content(prompt)
            return (getattr(resp, "text", None) or "").strip()

        except exceptions.ResourceExhausted as retry_e:
            msg = str(retry_e).strip() or first_err
            logger.error("Gemini quota exceeded: %s", msg)

            if "limit: 0" in msg and "free_tier" in msg.lower():
                return (
                    "I'm having trouble connecting right now. "
                    "Could you try again in a moment?"
                )

            return "I'm experiencing technical difficulties. Please try again shortly."

        except Exception as retry_err:
            logger.error("Retry failed: %s", retry_err)
            return "Something went wrong. Could you please try asking again?"

    except Exception as e:
        logger.error("Generation error: %s", e)
        return "I'm having a technical issue. Please try again in a moment."
