"""
Agent handoff flow - Collect basic contact details for non-digital products.
"""

from typing import Dict

from src.chatbot.validation import raise_if_errors, require_str, validate_email, validate_phone_ug


class AgentHandoffFlow:
    def __init__(self, db):
        self.db = db

    async def start(self, user_id: str, initial_data: Dict) -> Dict:
        collected = dict(initial_data or {})
        return {
            "response": {
                "type": "form",
                "message": "Please share your details and we will connect you to an agent.",
                "fields": [
                    {"name": "full_name", "label": "Full Name", "type": "text", "required": True},
                    {"name": "phone_number", "label": "Phone Number", "type": "tel", "required": True, "placeholder": "07XX XXX XXX"},
                    {"name": "email", "label": "Email Address", "type": "email", "required": True},
                    {
                        "name": "preferred_contact",
                        "label": "Preferred Contact",
                        "type": "select",
                        "options": ["Phone", "Email", "WhatsApp"],
                        "required": True,
                    },
                    {"name": "notes", "label": "Notes (optional)", "type": "textarea", "required": False},
                ],
            },
            "next_step": 0,
            "collected_data": collected,
        }

    async def process_step(self, user_input, current_step: int, collected_data: Dict, user_id: str) -> Dict:
        payload = user_input if isinstance(user_input, dict) else {}
        data = dict(collected_data or {})

        if payload and "_raw" not in payload:
            errors: Dict[str, str] = {}
            full_name = require_str(payload, "full_name", errors, label="Full Name")
            phone_number = validate_phone_ug(payload.get("phone_number", ""), errors, field="phone_number")
            email = validate_email(payload.get("email", ""), errors, field="email")
            preferred_contact = require_str(payload, "preferred_contact", errors, label="Preferred Contact")
            notes = (payload.get("notes") or "").strip()
            raise_if_errors(errors)

            handoff = {
                "full_name": full_name,
                "phone_number": phone_number,
                "email": email,
                "preferred_contact": preferred_contact,
                "notes": notes,
                "product_name": data.get("product_name"),
                "product_url": data.get("product_url"),
            }
            data["handoff"] = handoff

            lead = self.db.create_agent_handoff_lead(user_id=user_id, data=handoff)

            return {
                "response": {
                    "type": "info",
                    "message": "Thanks. An agent will reach out shortly.",
                    "reference": getattr(lead, "id", None),
                },
                "complete": True,
                "collected_data": data,
            }

        return await self.start(user_id, data)
