"""Forced mock premium endpoints for Swagger testing."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.integrations.clients.mocks.premium_mocks.premium import MockPremiumClient

router = APIRouter(prefix="/api/v1/mock/premiums", tags=["Mock Premiums"])
mock_premium_client = MockPremiumClient()


class MockPremiumCalculateRequest(BaseModel):
    product_key: str = Field(..., description="Product identifier, e.g. personal_accident")
    data: Dict[str, Any] = Field(default_factory=dict, description="Premium calculation payload")


@router.post("/calculate")
async def calculate_mock_premium(request: MockPremiumCalculateRequest):
    try:
        return await mock_premium_client.calculate_premium(request.product_key, request.data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
