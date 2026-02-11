import json
import os
import logging
from dataclasses import dataclass
from typing import Any, Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Use the same family as the main generator for consistency.
INTENT_MODEL_NAME = "gemini-2.5-flash"


@dataclass
class IntentResult:
    label: str
    intent_type: str  # "NO_RETRIEVAL" | "INFORMATIONAL" | "OTHER"
    should_retrieve: bool


class IntentClassifier:
    """
    LLM-based intent classifier used as a fallback when simple heuristics
    cannot confidently detect greetings / small talk vs informational queries.

    It is intentionally lightweight: a single short prompt, JSON output, and
    no use of retrieval context.
    """

    def __init__(self, api_key_env: str = "GEMINI_API_KEY"):
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is missing; IntentClassifier cannot be used.")
        self.client = genai.Client(api_key=api_key)

    async def classify(self, message: str) -> Optional[IntentResult]:
        msg = (message or "").strip()
        if not msg:
            return None

        system_instruction = """
You are an intent classifier for the Old Mutual Uganda chatbot.

Your job is to decide whether a single user message is:
- GREETING      (e.g. "hi", "hello", "hey")
- SMALL_TALK    (e.g. "how are you", "what's up")
- THANKS        (e.g. "thanks", "thank you")
- GOODBYE       (e.g. "bye", "see you")
- HELP          (user asks for help without a clear topic)
- OFF_TOPIC     (personal/irrelevant questions not about Old Mutual or insurance)
- INFO_QUERY    (general informational question about Old Mutual, insurance, products, coverage, claims, processes)
- PRODUCT_QUERY (question clearly about a specific product or benefit)
- COMPARISON    (compare products, companies, or options)
- OTHER         (any other message)

You MUST respond with STRICT JSON using this shape:
{
    "label": "GREETING" | "SMALL_TALK" | "THANKS" | "GOODBYE" | "HELP" | "OFF_TOPIC" | "INFO_QUERY" | "PRODUCT_QUERY" | "COMPARISON" | "OTHER",
  "intent_type": "NO_RETRIEVAL" | "INFORMATIONAL",
  "should_retrieve": true | false
}

Rules:
- Use intent_type = "NO_RETRIEVAL" for GREETING, SMALL_TALK, THANKS, GOODBYE, HELP, OFF_TOPIC.
- Use intent_type = "INFORMATIONAL" only when the user is clearly asking for information.
- should_retrieve should be true only when intent_type = "INFORMATIONAL".
- For vague or short messages that are not clearly asking for information, prefer NO_RETRIEVAL.
""".strip()

        prompt = f'User message: "{msg}"\n\nReturn ONLY the JSON object, no explanation.'

        try:
            response = await self.client.aio.models.generate_content(
                model=INTENT_MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.0,
                    max_output_tokens=128,
                ),
            )
            text = (getattr(response, "text", "") or "").strip()
            if not text:
                logger.warning("IntentClassifier: empty response")
                return None

            # Extract the first JSON object from the text.
            obj = self._parse_json_object(text)
            if not isinstance(obj, dict):
                return None

            label = str(obj.get("label") or "OTHER").upper()
            intent_type = str(obj.get("intent_type") or "").upper()
            should_retrieve = bool(obj.get("should_retrieve", False))

            allowed_labels = {
                "GREETING",
                "SMALL_TALK",
                "THANKS",
                "GOODBYE",
                "HELP",
                "OFF_TOPIC",
                "INFO_QUERY",
                "PRODUCT_QUERY",
                "COMPARISON",
                "OTHER",
            }
            if label not in allowed_labels:
                label = "OTHER"

            if intent_type not in {"NO_RETRIEVAL", "INFORMATIONAL"}:
                # Default conservatively to INFORMATIONAL only when explicit.
                intent_type = "INFORMATIONAL" if should_retrieve else "NO_RETRIEVAL"

            return IntentResult(label=label, intent_type=intent_type, should_retrieve=should_retrieve)
        except Exception as e:
            logger.warning("IntentClassifier error: %s", e, exc_info=True)
            return None

    @staticmethod
    def _parse_json_object(text: str) -> Any:
        """
        Best-effort extraction of a JSON object from model text.
        """
        text = text.strip()
        # Fast path: the whole response is JSON.
        try:
            return json.loads(text)
        except Exception:
            pass

        # Fallback: find first '{' and last '}' and try to parse substring.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except Exception:
                return None
        return None


class SmallTalkResponder:
    """
    Uses the LLM to generate short, polite replies for NO_RETRIEVAL intents
    (greetings, thanks, small talk, goodbyes) without touching RAG.
    """

    def __init__(self, api_key_env: str = "GEMINI_API_KEY"):
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is missing; SmallTalkResponder cannot be used.")
        self.client = genai.Client(api_key=api_key)

    async def respond(self, message: str, label: str) -> str:
        msg = (message or "").strip()
        label_upper = (label or "").upper()

        system_instruction = """
You are MIA, the Old Mutual Uganda virtual assistant, answering ONLY greetings,
thanks, small talk, and goodbyes.

Rules:
- Reply in 1–2 short lines.
- Be warm and professional.
- Do NOT mention specific product names, benefits, prices, or policy details.
- Do NOT give financial advice.
- Gently invite the user to ask about Old Mutual products or services.
""".strip()

        prompt = f'User message: "{msg}"\n\nIntent label: {label_upper}\n\nReply conversationally for this small-talk intent.'

        try:
            response = await self.client.aio.models.generate_content(
                model=INTENT_MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.3,
                    max_output_tokens=120,
                ),
            )
            text = (getattr(response, "text", "") or "").strip()
            if not text:
                return "Hi, I’m MIA. How can I help you with Old Mutual products or services today?"
            return text
        except Exception as e:
            logger.warning("SmallTalkResponder error: %s", e, exc_info=True)
            return "Hi, I’m MIA. How can I help you with Old Mutual products or services today?"
