#!/usr/bin/env python3
"""Small offline validator for the TRV10 buyer payload shape."""
import json
import sys


def main() -> int:
    payload = json.load(sys.stdin)
    context = payload.get("context", {})
    intent = payload.get("message", {}).get("intent", {})
    required_context = {"domain", "action", "bap_id", "bap_uri", "transaction_id", "message_id", "timestamp"}
    missing = sorted(required_context - context.keys())
    if context.get("domain") != "ONDC:TRV10":
        missing.append("context.domain=ONDC:TRV10")
    if not intent.get("fulfillment", {}).get("stops"):
        missing.append("message.intent.fulfillment.stops")
    if missing:
        print(json.dumps({"valid": False, "missing": missing}))
        return 1
    print(json.dumps({"valid": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
