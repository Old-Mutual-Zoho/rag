from fastapi import APIRouter, HTTPException
from src.integrations.clients.mocks.mtn import MTNMockClient
from src.integrations.clients.mocks.airtel import AirtelMockClient
from src.integrations.contracts.payments import PaymentRequest, PaymentResponse

api = APIRouter()
payments_api = api


@api.post("/payments/initiate", tags=["Payments"])
async def initiate_payment(
    quote_id: str,
    provider: str,
    phone_number: str,
    amount: float,
    currency: str = "UGX",
):
    # Select integration client
    if provider.lower() == "mtn":
        client = MTNMockClient()
    elif provider.lower() == "airtel":
        client = AirtelMockClient()
    else:
        raise HTTPException(status_code=400, detail="Invalid provider")

    payment_request = PaymentRequest(
        reference=quote_id,
        phone_number=phone_number,
        amount=amount,
        currency=currency,
        description=f"Payment for quote {quote_id}",
    )

    payment_response: PaymentResponse = client.initiate_payment(payment_request)

    return {
        "status": payment_response.status,
        "message": payment_response.message,
        "provider_reference": payment_response.provider_reference,
        "amount": payment_response.amount,
        "currency": payment_response.currency
    }
