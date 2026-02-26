import os
import hmac
import logging

from fastapi import Header, HTTPException, status, Request
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_ALLOWLIST_PATHS = {
    "/",  # optional
    "/health",
    "/docs",
    "/docs/oauth2-redirect",
    "/openapi.json",
    "/redoc",
    "/api/v1/agent/slack/events",
}


def get_api_keys():
    keys = os.getenv("API_KEYS", "")
    return [k.strip() for k in keys.split(",") if k.strip()]


async def api_key_protection(
    request: Request = None,  # keep Request type so FastAPI injects it; default None for direct calls/tests
    x_api_key: str = Header(default=None, alias="X-API-KEY"),
):
    # DEBUG: print what FastAPI sees
    print("DEBUG: Received API Key from header:", x_api_key)
    debug = os.getenv("API_KEY_DEBUG", "").lower() in ("1", "true", "yes")
    path = request.url.path if request is not None else "<no-request>"
    if debug:
        logger.info("API key check: path=%s header_present=%s", path, bool(x_api_key))

    if request is not None and request.url.path in _ALLOWLIST_PATHS:
        if debug:
            logger.info("API key check: allowlisted path=%s", path)
        return

    valid_keys = get_api_keys()
    candidate = (x_api_key or "").strip()

    ok = bool(candidate) and any(hmac.compare_digest(candidate, k) for k in valid_keys)
    if debug:
        logger.info("API key check: path=%s ok=%s configured_keys=%d", path, ok, len(valid_keys))

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )
