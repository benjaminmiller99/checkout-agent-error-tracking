"""Capture failures that occur while an e-commerce agent prepares an order."""

import hashlib
import traceback
from collections.abc import Callable
from typing import Any

import infrai


def run_step(order_id: str, step: str, action: Callable[[], Any]) -> Any:
    """Run an agent action and preserve its exception after recording context."""
    try:
        return action()
    except Exception as exc:
        stable_id = hashlib.sha256(f"{order_id}:{step}".encode()).hexdigest()
        infrai.errors.capture(
            title=f"checkout-agent/{step}",
            message=str(exc),
            exception=traceback.format_exc(),
            level="error",
            fingerprint=["checkout-agent", step],
            context={"order_id": order_id, "step": step},
            idempotency_key=stable_id,
        )
        raise


def reserve_inventory() -> None:
    raise ValueError("SKU is no longer available for this order")


def main() -> None:
    try:
        run_step("order-1042", "reserve-inventory", reserve_inventory)
    except ValueError:
        print("Checkout-agent step recorded for review.")


if __name__ == "__main__":
    main()
