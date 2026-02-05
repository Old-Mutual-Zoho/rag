import os
import logging
from typing import Any, Dict, List
from google import genai
from google.genai import types

# Setup logging - essential for debugging RAG failures
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- SYSTEM SETTINGS ---
MODEL_NAME = "gemini-1.5-flash"  # Flash is the king of speed
SYSTEM_INSTRUCTION = """
You are MIA, the Senior Virtual Assistant for Old Mutual Uganda. You are an expert across all business lines:
General Insurance, Life Assurance, and Asset Management.

CORE PRODUCT CATALOG (Knowledge Base):
1. PERSONAL INSURANCE (PROTECTION):
   - Serenicare: Comprehensive medical (Inpatient, Outpatient, Dental, Optical, Maternity). Covers East Africa.
   - Motor: Motor Private, Motor Commercial, and Motor COMESA (Yellow Card for regional travel).
   - Travel Sure Plus: For international travel emergencies.
   - Domestic Package: Covers your home, contents, and domestic workers.
   - Personal Accident: Compensation for accidental death or disability.

2. SAVINGS & INVESTMENTS (WEALTH):
   - Unit Trusts: Money Market Fund (High liquidity), Balanced Fund, Umbrella Fund.
   - Dollar Unit Trust: Invest in USD (Min $1,000).
   - Sure Deal: 5-10 year savings plan with a guaranteed tax-free lump sum.
   - SOMESA Plus: Education plan for children 0-18 yrs. 5-10yr accumulation phase.
   - Private Wealth: Bespoke portfolios for High-Net-Worth individuals.

3. BUSINESS SOLUTIONS:
   - Office Compact: One-stop SME policy (Fire, Burglary, Liability).
   - Group Schemes: Group Life, Group Medical (Standard/Enhanced), and SME Life Pack.
   - Special Risks: Marine Cargo, Livestock, and Crop Insurance.

RESPONSE RULES:
- If asked "What do you offer?", provide a structured summary using the categories above.
- If asked about a specific product, use the 'Retrieved Data' for fine details (like USSD codes or specific waiting periods).
- TONE: Professional, sales-oriented, and helpful.
- FORMAT: Use bullet points and bold headers. Keep it under 10 lines.
""".strip()


class MiaGenerator:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("CRITICAL: GEMINI_API_KEY is missing from environment variables.")

        self.client = genai.Client(api_key=api_key)

    def _build_context(self, hits: List[Dict[str, Any]]) -> str:
        context_parts = []
        for h in hits:
            p = h.get("payload") or h
            title = p.get("title", "Product")
            heading = p.get("section_heading", "")
            text = p.get("text", "")
            chunk = f"[{title} | {heading}]: {text}"
            context_parts.append(chunk)
        return "\n\n".join(context_parts)

    async def generate(self, question: str, hits: List[Dict[str, Any]]) -> str:
        # BUILD CONTEXT: If no hits, we just send an empty string.
        # Gemini will then rely on its System Instructions (The Master Catalog).
        context = self._build_context(hits) if hits else "No specific documents found for this query."

        try:
            response = await self.client.models.generate_content_async(
                model="gemini-1.5-flash",
                #  We always call the model. The model decides if it knows enough to answer.
                contents=f"Question: {question}\n\nRetrieved Data:\n{context}",
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.2,
                    max_output_tokens=500  # Slightly more tokens for full catalog lists
                )
            )
            answer = response.text.strip()
            return answer

        except Exception as e:
            logger.error(f"GenAI Error: {e}")
            return "I'm here to help! Could you please rephrase that so I can get you the right details?"
