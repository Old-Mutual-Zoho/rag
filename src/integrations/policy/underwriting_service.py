"""
Underwriting Service for Partner API Integration

This module provides functions to interact with external partner underwriting APIs.
"""

import httpx
from typing import Dict, Any

class UnderwritingService:
    def __init__(self, base_url: str, api_key: str = None):
        self.base_url = base_url
        self.api_key = api_key

    async def submit_underwriting(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls the partner underwriting API with the provided payload.
        """
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/underwriting", json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
