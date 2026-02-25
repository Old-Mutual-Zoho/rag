"""
MTN Mobile Money — MOCK client.

⚠️  This is a mock implementation for development and testing.
    Replace with the real MTN MoMo API client once credentials are available.
    All methods return realistic-looking fake data with configurable
    success/failure scenarios via the MTNMockClient constructor.
"""

import logging
import random
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.integrations.contracts.interfaces import (
    Beneficiary,
    CustomerProfile,
    KYCStatus,
    MobileMoneyProvider,
    PaymentRequest,
    PaymentResponse,
    PaymentStatus,
    PolicyApplication,
    PolicyStatus,
    Product,
    Provider,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

_MOCK_PRODUCTS: List[Product] = [
    Product(
        product_id="MTN-LIFE-001",
        name="MTN Bima Basic Life Cover",
        description="Affordable life cover for MTN subscribers and their families.",
        premium_amount=5000.0,
        currency="UGX",
        cover_amount=1_000_000.0,
        duration_months=12,
        eligible_age_min=18,
        eligible_age_max=65,
        features=["Death benefit", "Accidental death double payout", "No medical exam required"],
        exclusions=["Suicide within first 12 months", "Pre-existing terminal illness"],
    ),
    Product(
        product_id="MTN-LIFE-002",
        name="MTN Bima Family Shield",
        description="Extended family cover including spouse and up to 4 children.",
        premium_amount=12_000.0,
        currency="UGX",
        cover_amount=3_000_000.0,
        duration_months=12,
        eligible_age_min=18,
        eligible_age_max=60,
        features=["Death benefit", "Spouse cover", "Child cover up to age 21", "Hospital cash benefit"],
        exclusions=["War or civil unrest", "Intentional self-harm"],
    ),
    Product(
        product_id="MTN-HOSP-001",
        name="MTN Hospital Cash Plan",
        description="Daily cash payout for every night spent in hospital.",
        premium_amount=8_000.0,
        currency="UGX",
        cover_amount=500_000.0,
        duration_months=6,
        eligible_age_min=18,
        eligible_age_max=70,
        features=["UGX 50,000 per night in hospital", "ICU double benefit", "No waiting period for accidents"],
        exclusions=["Cosmetic procedures", "Drug or alcohol-related admissions"],
    ),
]


# ---------------------------------------------------------------------------
# Mock client
# ---------------------------------------------------------------------------

class MTNMockClient(MobileMoneyProvider):
    """
    Mock MTN MoMo client.

    Parameters
    ----------
    payment_success_rate : float
        Probability (0–1) that a payment will succeed. Default 0.95.
    kyc_auto_verify : bool
        If True, KYC verifications always succeed immediately. Default True.
    simulate_latency : bool
        If True, adds a log message simulating network delay. Default False.
    """

    def __init__(
        self,
        payment_success_rate: float = 0.95,
        kyc_auto_verify: bool = True,
        simulate_latency: bool = False,
    ):
        self._success_rate = payment_success_rate
        self._kyc_auto_verify = kyc_auto_verify
        self._simulate_latency = simulate_latency

        # In-memory stores (reset on restart)
        self._payments: Dict[str, PaymentResponse] = {}
        self._customers: Dict[str, CustomerProfile] = {}
        self._policies: Dict[str, PolicyApplication] = {}

        logger.info("[MTN MOCK] Client initialised (success_rate=%.0f%%)", payment_success_rate * 100)

    # ------------------------------------------------------------------
    # Provider identity
    # ------------------------------------------------------------------

    @property
    def provider(self) -> Provider:
        return Provider.MTN

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log_latency(self, operation: str) -> None:
        if self._simulate_latency:
            logger.debug("[MTN MOCK] Simulating network latency for %s", operation)

    def _should_succeed(self) -> bool:
        return random.random() < self._success_rate

    def _new_provider_ref(self) -> str:
        return f"MTN-{uuid.uuid4().hex[:12].upper()}"

    # ------------------------------------------------------------------
    # Payments
    # ------------------------------------------------------------------

    def initiate_payment(self, request: PaymentRequest) -> PaymentResponse:
        self._log_latency("initiate_payment")
        logger.info("[MTN MOCK] Initiating payment ref=%s amount=%s %s",
                    request.reference, request.amount, request.currency)

        if self._should_succeed():
            status = PaymentStatus.SUCCESS
            message = "Payment completed successfully."
        else:
            status = PaymentStatus.FAILED
            message = "Insufficient funds or subscriber declined."

        response = PaymentResponse(
            reference=request.reference,
            provider_reference=self._new_provider_ref(),
            status=status,
            amount=request.amount,
            currency=request.currency,
            message=message,
        )
        self._payments[request.reference] = response
        logger.info("[MTN MOCK] Payment %s → %s", request.reference, status)
        return response

    def check_payment_status(self, reference: str) -> PaymentResponse:
        self._log_latency("check_payment_status")
        if reference in self._payments:
            return self._payments[reference]

        # Unknown reference — return PENDING so callers can retry
        return PaymentResponse(
            reference=reference,
            provider_reference="UNKNOWN",
            status=PaymentStatus.PENDING,
            amount=0.0,
            currency="UGX",
            message="Transaction not found; may still be processing.",
        )

    def reverse_payment(self, reference: str, reason: str) -> PaymentResponse:
        self._log_latency("reverse_payment")
        if reference not in self._payments:
            raise ValueError(f"[MTN MOCK] Payment '{reference}' not found, cannot reverse.")

        original = self._payments[reference]
        reversed_response = PaymentResponse(
            reference=reference,
            provider_reference=self._new_provider_ref(),
            status=PaymentStatus.REVERSED,
            amount=original.amount,
            currency=original.currency,
            message=f"Reversed. Reason: {reason}",
        )
        self._payments[reference] = reversed_response
        logger.info("[MTN MOCK] Payment %s reversed. Reason: %s", reference, reason)
        return reversed_response

    # ------------------------------------------------------------------
    # Customer onboarding
    # ------------------------------------------------------------------

    def create_customer(self, profile: CustomerProfile) -> CustomerProfile:
        self._log_latency("create_customer")
        if not profile.customer_id:
            profile.customer_id = f"MTN-CUST-{uuid.uuid4().hex[:8].upper()}"

        profile.kyc_status = KYCStatus.PENDING
        profile.created_at = datetime.utcnow()
        self._customers[profile.customer_id] = profile

        logger.info("[MTN MOCK] Customer created id=%s name=%s",
                    profile.customer_id, profile.full_name)
        return profile

    def get_customer(self, customer_id: str) -> Optional[CustomerProfile]:
        self._log_latency("get_customer")
        customer = self._customers.get(customer_id)
        if not customer:
            logger.warning("[MTN MOCK] Customer not found id=%s", customer_id)
        return customer

    def update_customer(self, customer_id: str, updates: Dict[str, Any]) -> CustomerProfile:
        self._log_latency("update_customer")
        customer = self._customers.get(customer_id)
        if not customer:
            raise ValueError(f"[MTN MOCK] Customer '{customer_id}' not found.")

        for key, value in updates.items():
            if hasattr(customer, key):
                setattr(customer, key, value)
            else:
                customer.metadata[key] = value

        logger.info("[MTN MOCK] Customer updated id=%s fields=%s", customer_id, list(updates.keys()))
        return customer

    def verify_kyc(self, customer_id: str) -> KYCStatus:
        self._log_latency("verify_kyc")
        customer = self._customers.get(customer_id)
        if not customer:
            raise ValueError(f"[MTN MOCK] Customer '{customer_id}' not found.")

        if self._kyc_auto_verify:
            customer.kyc_status = KYCStatus.VERIFIED
            logger.info("[MTN MOCK] KYC auto-verified for customer %s", customer_id)
        else:
            customer.kyc_status = KYCStatus.PENDING
            logger.info("[MTN MOCK] KYC pending manual review for customer %s", customer_id)

        return customer.kyc_status

    def add_beneficiary(self, customer_id: str, beneficiary: Beneficiary) -> CustomerProfile:
        self._log_latency("add_beneficiary")
        customer = self._customers.get(customer_id)
        if not customer:
            raise ValueError(f"[MTN MOCK] Customer '{customer_id}' not found.")

        customer.beneficiaries.append(beneficiary)
        logger.info("[MTN MOCK] Beneficiary '%s' added to customer %s",
                    beneficiary.full_name, customer_id)
        return customer

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------

    def list_products(self) -> List[Product]:
        self._log_latency("list_products")
        return list(_MOCK_PRODUCTS)

    def get_product(self, product_id: str) -> Optional[Product]:
        self._log_latency("get_product")
        return next((p for p in _MOCK_PRODUCTS if p.product_id == product_id), None)

    # ------------------------------------------------------------------
    # Policy
    # ------------------------------------------------------------------

    def apply_for_policy(self, application: PolicyApplication) -> PolicyApplication:
        self._log_latency("apply_for_policy")
        if not application.application_id:
            application.application_id = f"MTN-POL-{uuid.uuid4().hex[:8].upper()}"

        application.status = PolicyStatus.ACTIVE
        application.created_at = datetime.utcnow()
        self._policies[application.application_id] = application

        logger.info("[MTN MOCK] Policy issued id=%s customer=%s product=%s",
                    application.application_id, application.customer_id, application.product_id)
        return application

    def get_policy(self, application_id: str) -> Optional[PolicyApplication]:
        self._log_latency("get_policy")
        return self._policies.get(application_id)

    def cancel_policy(self, application_id: str, reason: str) -> PolicyApplication:
        self._log_latency("cancel_policy")
        policy = self._policies.get(application_id)
        if not policy:
            raise ValueError(f"[MTN MOCK] Policy '{application_id}' not found.")

        policy.status = PolicyStatus.CANCELLED
        policy.metadata["cancellation_reason"] = reason
        policy.metadata["cancelled_at"] = datetime.utcnow().isoformat()

        logger.info("[MTN MOCK] Policy %s cancelled. Reason: %s", application_id, reason)
        return policy
