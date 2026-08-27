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
                "select_call_count": 0,
                "out_of_stock_flow": False,
                "sent_callbacks": set(),
                "stored_order": None,
                "stored_context": None,
                "created_at": None,
                "order_id": None,
                "lifecycle_task": None,
            }
        return self._store[transaction_id]

    def set_lifecycle_task(self, transaction_id: str, task: Any) -> None:
        self.get_or_create(transaction_id)["lifecycle_task"] = task

    def cancel_lifecycle_task(self, transaction_id: str) -> bool:
        task = self.get_or_create(transaction_id).get("lifecycle_task")
        if task and not task.done():
            task.cancel()
            logger.info(f"[LIFECYCLE TRACE] tx={transaction_id} cancelled pending lifecycle task")
            return True
        return False

    def store_order(self, transaction_id: str, order: Dict[str, Any], context: Dict[str, Any], created_at: str, order_id: str):
        session = self.get_or_create(transaction_id)
        session["stored_order"] = order
        session["stored_context"] = context.copy()
        session["created_at"] = created_at
        session["order_id"] = order_id
        logger.info(f"[LIFECYCLE TRACE] tx={transaction_id} stored order id={order_id}")

    def get_stored_order(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        return self.get_or_create(transaction_id).get("stored_order")

    def get_stored_context(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        return self.get_or_create(transaction_id).get("stored_context")

    def get_created_at(self, transaction_id: str) -> Optional[str]:
        return self.get_or_create(transaction_id).get("created_at")

    def get_order_id(self, transaction_id: str) -> Optional[str]:
        return self.get_or_create(transaction_id).get("order_id")

    def increment_select(self, transaction_id: str) -> int:
        session = self.get_or_create(transaction_id)
        session["select_call_count"] += 1
        return session["select_call_count"]

    def get_select_count(self, transaction_id: str) -> int:
        return self.get_or_create(transaction_id).get("select_call_count", 0)

    def mark_out_of_stock_flow(self, transaction_id: str) -> None:
        self.get_or_create(transaction_id)["out_of_stock_flow"] = True

    def is_out_of_stock_flow(self, transaction_id: str) -> bool:
        return bool(self.get_or_create(transaction_id).get("out_of_stock_flow"))

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
                state = RET10_FULFILLMENT_STATE["OUT_FOR_DELIVERY"]
            else:
                state = RET10_FULFILLMENT_STATE["DELIVERED"]

        session["current_state"] = state
        logger.info(f"[LIFECYCLE TRACE] tx={transaction_id} status_call={count} -> state={state}")
        return state

    def record_callback(self, transaction_id: str, action: str, state_code: Optional[str] = None):
        session = self.get_or_create(transaction_id)
        key = f"{action}:{state_code}" if state_code else action
        session["sent_callbacks"].add(key)
        logger.info(f"[LIFECYCLE TRACE] tx={transaction_id} recorded callback: {key}")


lifecycle_tracker = LifecycleTracker()
