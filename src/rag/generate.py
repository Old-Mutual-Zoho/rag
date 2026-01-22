"""
Answer generation utilities (LLM) for the RAG pipeline.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List
import google.generativeai as genai
from google.api_core import exceptions


def build_context(hits: List[Dict[str, Any]], *, max_chars: int = 6000) -> str:
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
        question: Original user question (to check if it's asking for general definition)

    Returns:
        Dict with analysis: has_general_info, product_names, categories, etc.
    """
    product_names = set()
    categories = set()
    has_general_info = False
    has_specific_products = False
    general_info_indicators = 0

    question_lower = question.lower()
    is_general_question = any(phrase in question_lower for phrase in ["what is", "what are", "explain", "define", "tell me about", "how does"])

    for h in hits:
        payload = h.get("payload") or {}
        text = payload.get("text", "").lower()
        doc_type = payload.get("type", "")
        chunk_type = payload.get("chunk_type", "")

        # Check if this looks like a general information page/article
        # Look for general definitions, not product-specific info
        if doc_type in ("article", "info_page"):
            # Check if the text actually contains a general definition
            if any(
                phrase in text[:500]
                for phrase in [
                    "is a type of",
                    "refers to",
                    "is defined as",
                    "generally",
                    "in general",
                    "typically",
                ]
            ):
                has_general_info = True
                general_info_indicators += 1

        # Check for FAQ or overview chunks that might have general info
        if chunk_type in ("faq", "overview") and doc_type != "product":
            if any(phrase in text[:300] for phrase in ["what is", "what are", "refers to"]):
                has_general_info = True
                general_info_indicators += 1

        # Check for specific products
        if doc_type == "product":
            has_specific_products = True
            product_name = payload.get("title", "")
            if product_name:
                product_names.add(product_name)
            category = payload.get("category", "")
            if category:
                categories.add(category)

    # If user asked a general question but we only have specific products, flag it
    only_specific_products = is_general_question and has_specific_products and not has_general_info and general_info_indicators == 0

    return {
        "has_general_info": has_general_info,
        "has_specific_products": has_specific_products,
        "only_specific_products": only_specific_products,
        "product_names": list(product_names),
        "categories": list(categories),
        "is_general_question": is_general_question,
    }


def generate_with_gemini(
    *,
    question: str,
    hits: List[Dict[str, Any]],
    model: str,  # Named 'model' to fix the TypeError
    api_key_env: str = "GEMINI_API_KEY",
) -> str:
    """
    Generate an answer using Gemini with improved handling for partial information
    and clarification questions.
    """
    key = os.environ.get(api_key_env)
    if not key:
        raise RuntimeError(f"{api_key_env} is not set")

    genai.configure(api_key=key)
    context = build_context(hits)

    # Analyze the context to understand what information is available
    analysis = _analyze_context(hits, question)

    # Build a smarter prompt based on context analysis
    if analysis["only_specific_products"]:
        # Only specific products found, no general definition
        product_list = ", ".join(analysis["product_names"][:3])
        if len(analysis["product_names"]) > 3:
            product_list += f", and {len(analysis['product_names']) - 3} more"

        prompt = (
            "You are a helpful assistant for Old Mutual Uganda.\n"
            "The user asked a general question, but you only have information about specific "
            "Old Mutual Uganda products, not a general definition.\n\n"
            f"Question: {question}\n\n"
            f"Available context (specific products only):\n{context}\n\n"
            f"Products mentioned in context: {product_list}\n\n"
            "Instructions:\n"
            "1. Start directly with the product name and information. DO NOT include introductory statements "
            "like 'We are happy to provide...' or 'This product is designed to...' at the beginning. "
            "Just start with '[Product Name] is...' or similar direct statements.\n"
            "2. Provide a natural, well-formatted answer about the specific products available.\n"
            "3. Format your answer clearly with sections, but DO NOT use question headers like "
            "'What is X:' or 'Who is eligible:'. Instead, write naturally in paragraph form or use "
            "clear section headings like 'Overview', 'Eligibility', 'Benefits'.\n"
            "4. DO NOT start with phrases like 'Based on the context provided' or 'According to the context'. "
            "Just provide the information directly and naturally.\n"
            "5. At the end, ask an encouraging, product-focused question that motivates the user to learn more, "
            "such as:\n"
            "   - 'Would you like to explore how [product name] can help you achieve your goals?'\n"
            "   - 'I'd be happy to help you understand how [product name] could benefit you. What would you like to know?'\n"
            "   - 'Ready to learn more about [product name] and see if it's right for you?'\n"
            "6. Be friendly, professional, and encouraging - focus on helping the user discover value.\n\n"
            "Your response:"
        )
    else:
        # Standard prompt for when we have general info or no products
        prompt = (
            "You are a helpful assistant for Old Mutual Uganda.\n"
            "Answer the question using ONLY the context below.\n\n"
            "Formatting guidelines:\n"
            "1. Start directly with the answer. DO NOT include introductory statements "
            "like 'We are happy to provide...' or 'This product is designed to...' at the beginning. "
            "Just start with the information directly (e.g., '[Product/Topic] is...').\n"
            "2. DO NOT start with phrases like 'Based on the context provided' or 'According to the context'. "
            "Just provide the information directly and naturally.\n"
            "3. Format your answer clearly with sections, but DO NOT use question headers like "
            "'What is X:' or 'Who is eligible:'. Instead, write naturally in paragraph form or use "
            "clear section headings like 'Overview', 'Eligibility', 'Benefits'.\n"
            "4. If the context does not contain enough information to fully answer the question:\n"
            "   - Acknowledge what information IS available\n"
            "   - Clearly state what information is missing\n"
            "   - Ask an encouraging, helpful question to better assist the user\n"
            "5. Be friendly, professional, and encouraging - focus on helping the user discover value.\n\n"
            f"Question:\n{question}\n\n"
            f"Context:\n{context}\n"
        )

    # Use a specific model instance
    m = genai.GenerativeModel(model)

    # Attempt generation with a single retry on rate limit
    try:
        resp = m.generate_content(prompt)
        return (getattr(resp, "text", None) or "").strip()
    except exceptions.ResourceExhausted:
        # If we hit the 429 quota error, wait 5 seconds and try one last time
        time.sleep(5)
        try:
            resp = m.generate_content(prompt)
            return (getattr(resp, "text", None) or "").strip()
        except Exception:
            return "Error: API quota exceeded. Please try again in a moment."
    except Exception as e:
        return f"An error occurred: {str(e)}"
