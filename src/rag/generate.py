import os
import logging
import asyncio
from typing import Any, Dict, List
from google import genai
from google.genai import types

# Setup logging - essential for debugging RAG failures
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- SYSTEM SETTINGS ---
MODEL_NAME = "gemini-1.5-flash"  # Flash is the king of speed
SYSTEM_INSTRUCTION = """
You are MIA, a friendly Old Mutual Uganda assistant.
Tone: Warm, conversational, WhatsApp-style.
Style: Short (3-10 lines), use 1-2 emojis (✅, 🛡️, 🚫, 💰).
Rules:
- Ground your answer ONLY in the 'Available Info'.
- If the info is missing or irrelevant, say you don't have that specific detail and ask a short clarifying question.
- Never say "Based on the info provided."
""".strip()


class MiaGenerator:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("CRITICAL: GEMINI_API_KEY is missing from environment variables.")

        self.client = genai.Client(api_key=api_key)

    def _build_context(self, hits: List[Dict[str, Any]]) -> str:
        """
        Extracts raw text and filters out metadata noise to save tokens/speed.
        """
        parts = []
        for i, h in enumerate(hits, start=1):
            p = h.get("payload") or {}
            text = (p.get("text") or "").strip()
            if text:
                # Format: [Source ID] Title/Heading: Body
                heading = p.get("section_heading") or p.get("title") or "Info"
                parts.append(f"[{i}] {heading}: {text}")

        return "\n".join(parts)

    async def generate(self, question: str, hits: List[Dict[str, Any]]) -> str:
        """
        The core engine: Safeguards -> Context Building -> Async Generation.
        """
        # 1. EMPTY CONTEXT SAFEGUARD
        # If your retriever (Qdrant) returns nothing, don't even call the LLM.
        if not hits:
            logger.info("Safeguard triggered: Zero hits from retriever.")
            return "I couldn't find specific details on that in our records. Could you tell me more about what you're looking for? ✨"

        context = self._build_context(hits)

        # 2. IRRELEVANT DATA SAFEGUARD
        # If the combined text is too short to be useful (e.g., just noise)
        if len(context) < 20:
            return "I'm having trouble finding the right information for that. Which product are you interested in? 🛡️"

        try:
            # 3. ASYNC GENERATION WITH TIMEOUT
            # If Gemini hangs, we kill the request at 8 seconds to preserve UX.
            response = await asyncio.wait_for(
                self.client.models.generate_content_async(
                    model=MODEL_NAME,
                    contents=f"Available Info:\n{context}\n\nUser Question: {question}",
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0.2,  # Stays factual and fast
                        max_output_tokens=300,  # Keeps it concise
                    )
                ),
                timeout=8.0
            )

            answer = response.text.strip()
            return answer if answer else "I'm here to help, but I need a bit more detail on that question! 👋"

        except asyncio.TimeoutError:
            logger.error("Latency Alert: Gemini took > 8 seconds.")
            return "I'm experiencing a slight delay. Please try again in a moment! ⏳"

        except Exception as e:
            logger.error(f"Execution Error: {str(e)}")
            # Handle the specific 'ResourceExhausted' (Quota) error
            if "429" in str(e) or "quota" in str(e).lower():
                return "I'm a bit busy at the moment! Could you ask that again in 30 seconds? 🚀"
            return "I hit a technical snag. Give me a moment and try again? 🛠️"
