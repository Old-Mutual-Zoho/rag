"""
Answer generation utilities (LLM) for the RAG pipeline.
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


def _analyze_context(hits: List[Dict[str, Any]], question: str) -> Dict[str, Any]:
    """
    Analyze retrieved context to understand what type of information is available.

    Args:
        hits: Retrieved chunks
        question: Original user question

    Returns:
        Dict with analysis: has_general_info, product_names, categories, etc.
    """
    product_names = set()
    categories = set()
    has_general_info = False
    has_specific_products = False

    question_lower = question.lower()
    is_general_question = any(phrase in question_lower for phrase in ["what is", "what are", "explain", "define", "tell me about", "how does"])

    for h in hits:
        payload = h.get("payload") or {}
        # text = payload.get("text", "").lower()
        doc_type = payload.get("type", "")
        chunk_type = payload.get("chunk_type", "")

        # Check for general information
        if doc_type in ("article", "info_page", "overview"):
            has_general_info = True

        if chunk_type in ("faq", "overview", "definition"):
            has_general_info = True

        # Check for specific products
        if doc_type == "product":
            has_specific_products = True
            product_name = payload.get("title", "")
            if product_name:
                product_names.add(product_name)
            category = payload.get("category", "")
            if category:
                categories.add(category)

    # Determine if we only have specific products for a general question
    only_specific_products = is_general_question and has_specific_products and not has_general_info

    return {
        "has_general_info": has_general_info,
        "has_specific_products": has_specific_products,
        "only_specific_products": only_specific_products,
        "product_names": list(product_names),
        "categories": list(categories),
        "is_general_question": is_general_question,
    }


def _build_prompt(question: str, context: str, analysis: Dict[str, Any]) -> str:
    """
    Build an appropriate prompt based on context analysis.
    """

    if analysis["only_specific_products"]:
        # User asked general question but we only have specific product info
        product_list = ", ".join(analysis["product_names"][:3])
        if len(analysis["product_names"]) > 3:
            product_list += f", and {len(analysis['product_names']) - 3} more"

        return f"""You are a helpful assistant for Old Mutual Uganda.

The user asked a general question, but the available information is about specific products.

Question: {question}

Available Products: {product_list}

Context:
{context}

Instructions:
- Provide helpful information about the relevant Old Mutual Uganda products
- Use clear headings and bullet points where appropriate
- Be concise and professional
- End with a helpful question to assist the user further, such as:
  "Would you like details about any specific product?"
  "Which of these products would you like to know more about?"

Answer:"""

    else:
        # Standard case: answer from available context
        return f"""You are a helpful assistant for Old Mutual Uganda.

Answer the question using the context provided below. Be accurate, concise, and helpful.

Question: {question}

Context:
{context}

Instructions:
- Answer directly and naturally
- Use clear formatting with headings and bullet points where helpful
- If the context doesn't fully answer the question, state what information is available and what's missing
- Be professional and friendly
- Keep responses focused and relevant

Answer:"""


def generate_with_gemini(
    *,
    question: str,
    hits: List[Dict[str, Any]],
    model: str,
    api_key_env: str = "GEMINI_API_KEY",
) -> str:
    """
    Generate an answer using Gemini with context-aware prompting.

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

    # Build context and analyze it
    context = build_context(hits)
    analysis = _analyze_context(hits, question)

    # Build appropriate prompt
    prompt = _build_prompt(question, context, analysis)

    # Initialize model
    m = genai.GenerativeModel(model)

    # Generation with retry logic for rate limits
    try:
        resp = m.generate_content(prompt)
        return (getattr(resp, "text", None) or "").strip()

    except exceptions.ResourceExhausted as e:
        first_err = str(e).strip()
        logger.warning("Gemini ResourceExhausted on first call: %s", first_err)

        # Wait and retry once
        time.sleep(5)
        try:
            resp = m.generate_content(prompt)
            return (getattr(resp, "text", None) or "").strip()

        except exceptions.ResourceExhausted as retry_e:
            msg = str(retry_e).strip() or first_err
            logger.warning("Gemini ResourceExhausted on retry: %s", msg)

            # Check for free-tier quota issue
            if "limit: 0" in msg and "free_tier" in msg.lower():
                return (
                    "Error: Your Gemini free-tier quota is exhausted. "
                    "Please enable billing in Google AI Studio (https://aistudio.google.com) "
                    "or use an API key with available quota. "
                    "See: https://ai.google.dev/gemini-api/docs/rate-limits"
                )

            return f"Error: Gemini API quota exceeded. {msg[:500]}" + ("..." if len(msg) > 500 else "") + " Check your quota in Google AI Studio."

        except Exception as retry_err:
            logger.error("Retry failed: %s", retry_err)
            return f"Error: Request failed after retry. {type(retry_err).__name__}: {retry_err}"

    except Exception as e:
        logger.error("Generation error: %s", e)
        return f"Error generating answer: {type(e).__name__}: {str(e)}"
