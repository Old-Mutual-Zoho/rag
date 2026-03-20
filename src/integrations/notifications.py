from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self) -> None:
        self.smtp_host = os.getenv("SMTP_HOST", "")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_pass = os.getenv("SMTP_PASS", "")
        self.from_email = os.getenv("SMTP_FROM_EMAIL", self.smtp_user or "noreply@example.com")
        self.sms_url = os.getenv("SMS_API_URL", "")
        self.sms_token = os.getenv("SMS_API_TOKEN", "")

    def send_policy_notifications(
        self,
        *,
        user_email: Optional[str],
        phone_number: Optional[str],
        policy_data: Dict[str, Any],
        pdf_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        email_result = None
        sms_result = None

        if user_email:
            email_result = self.send_policy_email(user_email=user_email, policy_data=policy_data, pdf_path=pdf_path)
        if phone_number:
            sms_result = self.send_policy_sms(phone_number=phone_number, policy_data=policy_data)

        return {"email": email_result, "sms": sms_result}

    def send_policy_email(self, *, user_email: str, policy_data: Dict[str, Any], pdf_path: Optional[str] = None) -> Dict[str, Any]:
        if not self.smtp_host:
            logger.info("SMTP not configured; skipping policy email to %s", user_email)
            return {"sent": False, "reason": "smtp_not_configured"}

        msg = EmailMessage()
        msg["Subject"] = f"Your Old Mutual policy {policy_data.get('policy_id') or ''}".strip()
        msg["From"] = self.from_email
        msg["To"] = user_email
        msg.set_content(
            (
                "Your policy has been issued successfully.\n\n"
                f"Policy ID: {policy_data.get('policy_id')}\n"
                f"Quote ID: {policy_data.get('quote_id')}\n"
                f"Status: {policy_data.get('status')}\n"
            )
        )

        if pdf_path:
            path = Path(pdf_path)
            if path.exists():
                with path.open("rb") as f:
                    msg.add_attachment(
                        f.read(),
                        maintype="application",
                        subtype="pdf",
                        filename=path.name,
                    )

        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
            server.starttls()
            if self.smtp_user:
                server.login(self.smtp_user, self.smtp_pass)
            server.send_message(msg)
        return {"sent": True, "channel": "email", "to": user_email}

    def send_policy_sms(self, *, phone_number: str, policy_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.sms_url:
            logger.info("SMS API not configured; skipping SMS to %s", phone_number)
            return {"sent": False, "reason": "sms_not_configured"}

        payload = {
            "to": phone_number,
            "message": (
                f"Your Old Mutual policy {policy_data.get('policy_id')} is {policy_data.get('status')}. "
                f"Quote: {policy_data.get('quote_id')}."
            ),
        }
        headers = {"Authorization": f"Bearer {self.sms_token}"} if self.sms_token else {}
        response = requests.post(self.sms_url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        return {"sent": True, "channel": "sms", "to": phone_number}
