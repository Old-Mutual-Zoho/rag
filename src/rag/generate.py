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

def generate_with_gemini(
    *,
    question: str,
    hits: List[Dict[str, Any]],
    model: str,  # Named 'model' to fix the TypeError
    api_key_env: str = "GEMINI_API_KEY",
) -> str:
    """
    Generate an answer using Gemini with basic retry logic for 429 errors.
    """
    key = os.environ.get(api_key_env)
    if not key:
        raise RuntimeError(f"{api_key_env} is not set")

    genai.configure(api_key=key)
    context = build_context(hits)

    prompt = (
        "You are a helpful assistant for Old Mutual Uganda.\n"
        "Answer the question using ONLY the context below.\n"
        "If the context does not contain enough information, say that clearly.\n\n"
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