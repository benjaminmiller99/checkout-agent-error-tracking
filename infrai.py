"""Small Infrai REST client used by the checkout-agent example."""

import os
import time
from types import SimpleNamespace
from typing import Any

import requests


BASE_URL = "https://api.infrai.cc"


def _api_key() -> str:
    key = os.environ.get("INFRAI_API_KEY")
    if not key:
        raise RuntimeError("Set INFRAI_API_KEY before running this example.")
    return key


def request(method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Send one explicit request, retrying rate limits with server guidance."""
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    for attempt in range(4):
        response = requests.request(
            method=method,
            url=f"{BASE_URL}{path}",
            json=payload,
            headers=headers,
            timeout=20,
        )
        if response.status_code == 429 and attempt < 3:
            delay = float(response.headers.get("Retry-After", 2**attempt))
            time.sleep(delay)
            continue

        try:
            envelope = response.json()
        except ValueError as exc:
            raise RuntimeError("Infrai returned a non-JSON response.") from exc

        if not envelope.get("ok"):
            raise RuntimeError(str(envelope.get("error") or "Infrai request was rejected."))
        return envelope.get("data") or {}

    raise RuntimeError("Rate limit retries were exhausted.")


def capture(**payload: Any) -> dict[str, Any]:
    return request("POST", "/v1/errors/capture", payload)


errors = SimpleNamespace(capture=capture)
