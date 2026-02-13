"""
Guided mode - Structured conversation flows
"""

from typing import Dict
from datetime import datetime
from ..flows.product_discovery import ProductDiscoveryFlow
from ..flows.underwriting import UnderwritingFlow
from ..flows.quotation import QuotationFlow
from ..flows.payment import PaymentFlow
from ..flows.motor_private import MotorPrivateFlow
from ..flows.personal_accident import PersonalAccidentFlow
from ..flows.travel_insurance import TravelInsuranceFlow
from ..flows.serenicare import SerenicareFlow
from ..flows.dynamic_question_engine import DynamicQuestionEngineFlow


class GuidedMode:
    def __init__(self, state_manager, product_catalog, db):
        self.state_manager = state_manager
        self.catalog = product_catalog
        self.db = db

        # Initialize flows
        self.flows = {
            "journey": DynamicQuestionEngineFlow(product_catalog, db),
            "discovery": ProductDiscoveryFlow(product_catalog),
            "underwriting": UnderwritingFlow(db),
            "quotation": QuotationFlow(product_catalog, db),
            "payment": PaymentFlow(db),
            "personal_accident": PersonalAccidentFlow(product_catalog, db),
            "travel_insurance": TravelInsuranceFlow(product_catalog, db),
            "motor_private": MotorPrivateFlow(product_catalog, db),
            "serenicare": SerenicareFlow(product_catalog, db),
        }

    async def process(self, user_input, session_id: str, user_id: str) -> Dict:
        """Process one step in guided mode. user_input can be a string or a dict (form_data from frontend)."""

        # Get current state
        session = self.state_manager.get_session(session_id)

        if not session or not session.get("current_flow"):
            return {"error": "No active flow. Please start a flow first."}

        # Get the active flow
        flow = self.flows[session["current_flow"]]

        # Process current step
        result = await flow.process_step(
            user_input=user_input,
            current_step=session["current_step"],
            collected_data=session.get("collected_data", {}),
            user_id=user_id,
        )

        # Update state based on result
        if result.get("complete"):
            # Flow is complete, transition or end
            if result.get("next_flow"):
                self.state_manager.clear_form_draft(session_id, session["current_flow"])
                self.state_manager.set_flow(session_id, result["next_flow"])
                # Pass data needed by next flow (e.g. quote_id for payment)
                if result.get("collected_data"):
                    self.state_manager.update_session(session_id, {"collected_data": result["collected_data"]})
            else:
                self.state_manager.clear_form_draft(session_id, session["current_flow"])
                self.state_manager.switch_mode(session_id, "conversational")
        elif result.get("next_step") is not None:
            # Advance to next step
            self.state_manager.update_session(
                session_id, {"current_step": result["next_step"], "collected_data": result.get("collected_data", session.get("collected_data", {}))}
            )
            # Persist draft after each successful step to support resume.
            self.state_manager.save_form_draft(
                session_id,
                session["current_flow"],
                {
                    "session_id": session_id,
                    "flow": session["current_flow"],
                    "step": result.get("next_step", session.get("current_step", 0)),
                    "collected_data": result.get("collected_data", session.get("collected_data", {})),
                    "status": "in_progress",
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )

        return {
            "mode": "guided",
            "flow": session["current_flow"],
            "step": result.get("next_step", session["current_step"]),
            "response": result.get("response"),
            "complete": result.get("complete", False),
            "data": result.get("data"),
        }

    async def start_flow(self, flow_name: str, session_id: str, user_id: str, initial_data: Dict = None) -> Dict:
        """Start a new guided flow"""

        if flow_name not in self.flows:
            return {"error": f"Unknown flow: {flow_name}"}

        # Switch to guided mode
        self.state_manager.switch_mode(session_id, "guided", flow=flow_name)

        # Initialize flow
        flow = self.flows[flow_name]
        result = await flow.start(user_id, initial_data or {})

        return {"mode": "guided", "flow": flow_name, "step": 0, "response": result.get("response"), "data": result.get("data")}
