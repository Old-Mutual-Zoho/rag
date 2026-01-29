"""
Underwriting flow - Collect customer data and assess risk
"""

from typing import Dict
from datetime import datetime


class UnderwritingFlow:
    def __init__(self, db):
        self.db = db
        self.steps = ["personal_info", "coverage_details", "health_questions", "lifestyle_questions", "review_and_submit"]

    async def start(self, user_id: str, initial_data: Dict) -> Dict:
        """Start underwriting flow. user_id is the internal user UUID from the API."""
        # Get user info from database (by internal id; API resolves external id to UUID before calling flows)
        user = self.db.get_user_by_id(user_id)

        if user and user.kyc_completed:
            # Skip personal info if we have it
            return await self.process_step("", 1, {"user_id": user_id}, user_id)

        return await self.process_step("", 0, {"user_id": user_id}, user_id)

    async def process_step(self, user_input: str, current_step: int, collected_data: Dict, user_id: str) -> Dict:
        """Process underwriting step"""

        if current_step == 0:  # personal_info
            return {
                "response": {
                    "type": "form",
                    "message": "📋 Let's start with your basic information",
                    "fields": [
                        {"name": "full_name", "label": "Full Name", "type": "text", "required": True},
                        {"name": "date_of_birth", "label": "Date of Birth", "type": "date", "required": True},
                        {"name": "gender", "label": "Gender", "type": "select", "options": ["Male", "Female", "Other"]},
                        {"name": "occupation", "label": "Occupation", "type": "text", "required": True},
                        {"name": "email", "label": "Email", "type": "email", "required": False},
                    ],
                },
                "next_step": 1,
                "collected_data": collected_data,
            }

        elif current_step == 1:  # coverage_details
            # Parse and save personal info
            if user_input:
                import json

                personal_info = json.loads(user_input) if isinstance(user_input, str) else user_input
                collected_data.update(personal_info)

            return {
                "response": {
                    "type": "form",
                    "message": "💰 Tell us about the coverage you need",
                    "fields": [
                        {
                            "name": "sum_assured",
                            "label": "Sum Assured (UGX)",
                            "type": "number",
                            "min": 1000000,
                            "max": 500000000,
                            "required": True,
                            "help": "The amount your beneficiaries will receive",
                        },
                        {"name": "policy_term", "label": "Policy Term (years)", "type": "number", "min": 5, "max": 30, "required": True},
                        {"name": "beneficiaries", "label": "Beneficiary Name", "type": "text", "required": True},
                    ],
                },
                "next_step": 2,
                "collected_data": collected_data,
            }

        elif current_step == 2:  # health_questions
            # Save coverage details
            if user_input:
                import json

                coverage_info = json.loads(user_input) if isinstance(user_input, str) else user_input
                collected_data.update(coverage_info)

            return {
                "response": {
                    "type": "health_questionnaire",
                    "message": " A few health questions to assess your risk",
                    "questions": [
                        {
                            "id": "chronic_conditions",
                            "question": "Do you have any chronic medical conditions?",
                            "type": "yes_no_details",
                            "details_prompt": "Please specify the conditions",
                        },
                        {
                            "id": "medications",
                            "question": "Are you currently taking any regular medications?",
                            "type": "yes_no_details",
                            "details_prompt": "Please list the medications",
                        },
                        {
                            "id": "hospitalizations",
                            "question": "Have you been hospitalized in the past 5 years?",
                            "type": "yes_no_details",
                            "details_prompt": "Please provide details",
                        },
                        {"id": "family_history", "question": "Any family history of heart disease, diabetes, or cancer?", "type": "yes_no_details"},
                    ],
                },
                "next_step": 3,
                "collected_data": collected_data,
            }

        elif current_step == 3:  # lifestyle_questions
            # Save health info
            if user_input:
                import json

                health_info = json.loads(user_input) if isinstance(user_input, str) else user_input
                collected_data["health_info"] = health_info

            return {
                "response": {
                    "type": "form",
                    "message": "🏃 Just a few lifestyle questions",
                    "fields": [
                        {
                            "name": "smoker",
                            "label": "Do you smoke?",
                            "type": "select",
                            "options": ["No", "Yes - occasionally", "Yes - regularly"],
                            "required": True,
                        },
                        {
                            "name": "alcohol",
                            "label": "Alcohol consumption",
                            "type": "select",
                            "options": ["None", "Occasional", "Moderate", "Heavy"],
                            "required": True,
                        },
                        {
                            "name": "exercise",
                            "label": "Exercise frequency",
                            "type": "select",
                            "options": ["Sedentary", "1-2 times/week", "3-4 times/week", "5+ times/week"],
                            "required": True,
                        },
                        {
                            "name": "hazardous_activities",
                            "label": "Do you participate in hazardous activities? (e.g., skydiving, racing)",
                            "type": "yes_no_details",
                        },
                    ],
                },
                "next_step": 4,
                "collected_data": collected_data,
            }

        elif current_step == 4:  # review_and_submit
            # Save lifestyle info
            if user_input:
                import json

                lifestyle_info = json.loads(user_input) if isinstance(user_input, str) else user_input
                collected_data["lifestyle_info"] = lifestyle_info

            # Assess if human review is needed
            requires_review = self._assess_risk(collected_data)

            return {
                "response": {
                    "type": "review",
                    "message": "✅ Please review your information",
                    "summary": self._generate_summary(collected_data),
                    "requires_human_review": requires_review,
                    "next_action": "quotation" if not requires_review else "human_review",
                },
                "complete": True,
                "next_flow": "quotation" if not requires_review else None,
                "collected_data": collected_data,
                "data": {"requires_review": requires_review, "risk_score": self._calculate_risk_score(collected_data)},
            }

        return {"error": "Invalid step"}

    def _assess_risk(self, data: Dict) -> bool:
        """Determine if human underwriter review is needed"""
        # Complex conditions that require human review
        health_info = data.get("health_info", {})

        # Automatic flags for human review
        if health_info.get("chronic_conditions", {}).get("answer") == "yes":
            return True

        if health_info.get("hospitalizations", {}).get("answer") == "yes":
            return True

        # High sum assured
        if data.get("sum_assured", 0) > 100000000:  # Over 100M UGX
            return True

        # Age factors
        dob = data.get("date_of_birth")
        if dob:
            age = (datetime.now() - datetime.fromisoformat(dob)).days // 365
            if age > 60:
                return True

        return False

    def _calculate_risk_score(self, data: Dict) -> float:
        """Calculate risk score (0-100)"""
        score = 50  # Base score

        # Age factor
        dob = data.get("date_of_birth")
        if dob:
            age = (datetime.now() - datetime.fromisoformat(dob)).days // 365
            score += (age - 30) * 0.5  # Increase risk with age

        # Health factors
        health_info = data.get("health_info", {})
        if health_info.get("chronic_conditions", {}).get("answer") == "yes":
            score += 20

        # Lifestyle factors
        lifestyle = data.get("lifestyle_info", {})
        if lifestyle.get("smoker") in ["Yes - regularly"]:
            score += 15
        if lifestyle.get("alcohol") == "Heavy":
            score += 10

        return min(max(score, 0), 100)

    def _generate_summary(self, data: Dict) -> Dict:
        """Generate summary of collected data"""
        return {
            "personal": {"name": data.get("full_name"), "age": self._calculate_age(data.get("date_of_birth")), "occupation": data.get("occupation")},
            "coverage": {
                "sum_assured": f"UGX {data.get('sum_assured'):,}",
                "term": f"{data.get('policy_term')} years",
                "beneficiary": data.get("beneficiaries"),
            },
            "health_summary": self._summarize_health(data.get("health_info", {})),
            "lifestyle_summary": self._summarize_lifestyle(data.get("lifestyle_info", {})),
        }

    def _calculate_age(self, dob_str: str) -> int:
        """Calculate age from date of birth"""
        if not dob_str:
            return 0
        dob = datetime.fromisoformat(dob_str)
        return (datetime.now() - dob).days // 365

    def _summarize_health(self, health_info: Dict) -> str:
        """Summarize health information"""
        flags = []
        if health_info.get("chronic_conditions", {}).get("answer") == "yes":
            flags.append("chronic conditions")
        if health_info.get("medications", {}).get("answer") == "yes":
            flags.append("regular medications")

        return ", ".join(flags) if flags else "No significant health issues reported"

    def _summarize_lifestyle(self, lifestyle_info: Dict) -> str:
        """Summarize lifestyle factors"""
        factors = []
        if lifestyle_info.get("smoker") != "No":
            factors.append("smoker")
        if lifestyle_info.get("exercise") in ["Sedentary"]:
            factors.append("sedentary lifestyle")

        return ", ".join(factors) if factors else "Healthy lifestyle"
