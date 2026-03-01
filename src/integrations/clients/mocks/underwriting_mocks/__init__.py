"""Registry for product-specific underwriting mock builders."""

from __future__ import annotations

from typing import Any, Callable, Dict

from .default_mock import build_default_mock
from .personal_accident import build_personal_accident_mock
from .serenicare import build_serenicare_mock

MockBuilder = Callable[[Dict[str, Any], str], Dict[str, Any]]

_REGISTRY: Dict[str, MockBuilder] = {
    "serenicare": build_serenicare_mock,
    "personal_accident": build_personal_accident_mock,
    "general": build_default_mock,
}


def get_product_mock_builder(product_key: str) -> MockBuilder:
    """Return product-specific mock builder with safe fallback."""
    return _REGISTRY.get(product_key, build_default_mock)
