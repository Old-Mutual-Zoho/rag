import os
import logging
from typing import Any, Dict, List, Tuple
from google import genai
import google.generativeai as genai


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default text generation model for Google Gemini via google-genai.
# As of the current SDK, gemini-2.5-flash is a fast, general-purpose model.
MODEL_NAME = "gemini-2.5-flash"

SYSTEM_INSTRUCTION = """
You are MIA, the Senior Virtual Assistant for Old Mutual Uganda.
PROTOCOL:
1. ALWAYS prioritize 'Retrieved Data'. Cite: "According to our documentation..."
2. If context is empty, give a general overview and provide contact: 0800-100-900.
3. FORMAT: Bullet points, **bold** terms, under 12 lines.
4. TONE: Professional, friendly, sales-oriented.
""".strip()


class MiaGenerator:
    def __init__(
        self,
        max_context_chars: int = 8000,
        min_score: float = 0.65,
        max_sources: int = 5,
        temperature: float = 0.2  # Lowered for financial accuracy
    ):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("CRITICAL: GEMINI_API_KEY is missing.")

        self.client = genai.Client(api_key=api_key)
        self.max_context_chars = max_context_chars
        self.min_score = min_score
        self.max_sources = max_sources
        self.temperature = temperature

    def _build_context(self, hits: List[Dict[str, Any]]) -> Tuple[str, int, float]:
        if not hits:
            return "", 0, 0.0

        filtered_hits = [h for h in hits if h.get("score", 0) >= self.min_score]
        if not filtered_hits:
            return "", 0, 0.0

        filtered_hits.sort(key=lambda x: x.get("score", 0), reverse=True)
        avg_score = sum(h.get("score", 0) for h in filtered_hits) / len(filtered_hits)

        context_parts = []
        current_length = 0
        sources_used = 0

        for idx, h in enumerate(filtered_hits[:self.max_sources], 1):
            p = h.get("payload") or h
            chunk = f"[Source {idx}] **{p.get('title', 'Unknown')}**: {p.get('text', '')}\n"
            if current_length + len(chunk) > self.max_context_chars:
                break
            context_parts.append(chunk)
            current_length += len(chunk)
            sources_used += 1

        return "\n".join(context_parts), sources_used, avg_score

    async def generate(self, question: str, hits: List[Dict[str, Any]]) -> str:
        context, num_sources, avg_score = self._build_context(hits)

        context_note = (
            f"Use the {num_sources} sources below." if num_sources > 0
            else "No specific documents found. Provide a general response."
        )

        full_prompt = f"{context_note}\n\n**User Question:** {question}\n\n**Retrieved Data:**\n{context or 'None'}"

        try:
            # Use the async client wrapper provided by google-genai.
            # Docs: https://googleapis.github.io/python-genai/
            response = await self.client.aio.models.generate_content(
                model=MODEL_NAME,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=self.temperature,
                    max_output_tokens=600,
                ),
            )

            text = (getattr(response, "text", "") or "").strip()
            if not text:
                logger.warning("GenAI returned empty text response.")
                return "I'm having trouble retrieving those details. Please call 0800-100-900 for immediate help."

            return text

        except Exception as e:
            logger.error(f"GenAI error: {e}", exc_info=True)
            return "I'm having trouble retrieving those details. Please call 0800-100-900 for immediate help."
