import logging
from typing import Dict, Any, Optional
from app.ondc.bpp.order_builder import RET10_FULFILLMENT_STATE

logger = logging.getLogger(__name__)


class LifecycleTracker:
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def get_or_create(self, transaction_id: str) -> Dict[str, Any]:
        if transaction_id not in self._store:
            self._store[transaction_id] = {
                "transaction_id": transaction_id,
                "current_state": "CREATED",
                "status_call_count": 0,
                "update_call_count": 0,
                "sent_callbacks": set(),
            }
        return self._store[transaction_id]

    def advance_status_state(self, transaction_id: str, requested_state: Optional[str] = None) -> str:
        session = self.get_or_create(transaction_id)
        session["status_call_count"] += 1
        count = session["status_call_count"]

        if requested_state and requested_state not in [RET10_FULFILLMENT_STATE["PACKED"], RET10_FULFILLMENT_STATE["PENDING"]]:
            state = requested_state
        else:
            if count == 1:
                state = RET10_FULFILLMENT_STATE["PACKED"]
            elif count == 2:
                state = RET10_FULFILLMENT_STATE["AGENT_ASSIGNED"]
            elif count == 3:
                state = RET10_FULFILLMENT_STATE["PICKED_UP"]
            elif count == 4:
                state = RET10_FULFILLMENT_STATE["RTO_INITIATED"]
            else:
                state = RET10_FULFILLMENT_STATE["RTO_DELIVERED"]

        session["current_state"] = state
        logger.info(f"[LIFECYCLE TRACE] tx={transaction_id} status_call={count} -> state={state}")
        return state

    def record_callback(self, transaction_id: str, action: str, state_code: Optional[str] = None):
        session = self.get_or_create(transaction_id)
        key = f"{action}:{state_code}" if state_code else action
        session["sent_callbacks"].add(key)
        logger.info(f"[LIFECYCLE TRACE] tx={transaction_id} recorded callback: {key}")


lifecycle_tracker = LifecycleTracker()
