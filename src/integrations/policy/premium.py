"""Premium policy selector service."""

from __future__ import annotations

import os
from typing import Any, Dict

from src.integrations.clients.mocks.premium_mocks.premium import MockPremiumClient
from src.integrations.clients.real_http.premium import RealPremiumClient
from src.integrations.contracts.premium import PremiumContract


class PremiumService:
    """Select mock vs real premium client based on env policy."""

    def __init__(
        self,
        mock_client: PremiumContract | None = None,
        real_client: PremiumContract | None = None,
    ) -> None:
        self.mock_client = mock_client or MockPremiumClient()
        self.real_client = real_client or RealPremiumClient()

    async def calculate(self, product_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._select_client().calculate_premium(product_key, payload)

    def calculate_sync(self, product_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._select_client().calculate_premium_sync(product_key, payload)

    @staticmethod
    def _select_mode() -> str:
        return os.getenv("PREMIUM_CLIENT_MODE", "real").strip().lower()

    def _select_client(self) -> PremiumContract:
        if self._select_mode() == "mock":
            return self.mock_client
        return self.real_client


premium_service = PremiumService()
