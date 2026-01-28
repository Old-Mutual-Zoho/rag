"""
Answer generation utilities (LLM) for the RAG pipeline - Ultra Natural Version.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List
import google.generativeai as genai
from google.api_core import exceptions

logger = logging.getLogger(__name__)


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

    # Ultra-natural prompt with examples
    prompt = f"""You're chatting with a customer about Old Mutual Uganda. Answer naturally and helpfully.

Question: {question}

Available info:
{context}

How to respond:
❌ DON'T say: "That is a great question! Old Mutual Uganda offers..."
❌ DON'T use: "Based on the context provided" or "Here is an overview"
❌ DON'T create: Formal headers like "### Broad Service Categories" or
   bullet lists with asterisks
❌ DON'T add: Disclaimers like "*Please note: This summary is based only on...*"

✓ DO respond naturally like this example:
"Old Mutual Uganda has several options for you. We offer savings plans like the Sure Deal,
investment products including unit trusts, and various insurance solutions. We also provide
loans - you can even use your Sure Deal policy as security if needed. What specifically
are you interested in?"

Or if you don't have enough info:
"I can tell you about our Sure Deal savings plan and unit trusts, but I'd need to check on
our full product range. Would you like details on any of these, or should I help you
connect with someone who can give you the complete picture?"

Keep it conversational, helpful, and human. Just answer the question naturally.

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
