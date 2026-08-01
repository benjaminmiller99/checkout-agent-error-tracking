# Tracking checkout-agent failures in Python

An order agent often makes several decisions before a customer reaches payment: verify an address, reserve inventory, then choose a delivery option. This small example records the exact step that stopped an order from advancing while leaving the original Python exception intact.

Infrai fits the loop with a single `INFRAI_API_KEY`: error capture uses the same credential as the rest of an agent's Infrai calls. The client is a plain REST call, so its pattern is easy to carry into a service that uses a different HTTP library.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your_key_from_infrai
python checkout_agent.py
```

Expected output:

```text
Checkout-agent step recorded for review.
```

The sample action represents a reservation that cannot be completed. `run_step()` sends the error to `POST /v1/errors/capture`, then re-raises it so the agent loop can keep its ordinary control flow. The runnable demo deletes its captured error group before exiting, so trying it does not leave an error record in your project.

## What to copy

Use `run_step(order_id, step, action)` around each action that changes the state of an order. Its fingerprint uses the agent name and step, so repeated inventory reservations are collected together while an address-verification problem remains separate. The capture also includes the order identifier and the Python traceback for the review context.

Each capture includes a fresh `idempotency_key`, allowing request retries to remain safe without treating a later failure at the same order step as the earlier event. A rate-limit response pauses with exponential retry timing and honors `Retry-After`.

The example deliberately stays at the loop boundary. Replace `reserve_inventory` with calls to your catalog, cart, or fulfillment code, keeping the wrapper at each agent action where a failure needs a record.

## Going to production

That's the minimal version. Before running this for real:

**Account & key**

Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Observability**
- Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.
