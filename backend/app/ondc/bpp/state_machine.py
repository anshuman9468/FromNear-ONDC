import logging
from typing import Dict, Any, Optional
from sqlalchemy import select

from app.ondc.bpp.order_builder import RET10_FULFILLMENT_STATE

logger = logging.getLogger(__name__)


class LifecycleTracker:
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _durable_enabled() -> bool:
        from app.core.settings import settings

        return bool(settings.ONDC_BPP_DURABLE_STATE)

    @staticmethod
    def _durable_fields() -> tuple[str, ...]:
        return (
            "transaction_id",
            "current_state",
            "status_call_count",
            "update_call_count",
            "select_call_count",
            "track_requested",
            "out_of_stock_flow",
            "rto_flow",
            "sent_callbacks",
            "stored_order",
            "stored_context",
            "created_at",
            "order_id",
            "cancelled",
            "issue_requests",
        )

    def _load_durable(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        if not self._durable_enabled():
            return None
        try:
            from app.core.database import SessionLocal
            from app.models.bpp_lifecycle_state import BppLifecycleState

            with SessionLocal() as db:
                row = db.scalar(
                    select(BppLifecycleState).where(
                        BppLifecycleState.transaction_id == transaction_id
                    )
                )
                if not row:
                    return None
                state = dict(row.state or {})
                state["sent_callbacks"] = set(state.get("sent_callbacks", []))
                return state
        except Exception as exc:  # local development must retain in-memory behavior
            logger.warning("Durable BPP state read unavailable: %s", exc)
            return None

    def _persist_durable(self, transaction_id: str) -> None:
        if not self._durable_enabled():
            return
        try:
            from app.core.database import SessionLocal
            from app.models.bpp_lifecycle_state import BppLifecycleState

            current = self._store[transaction_id]
            durable = {
                key: current.get(key)
                for key in self._durable_fields()
                if key in current and key != "transaction_id"
            }
            durable["transaction_id"] = transaction_id
            durable["sent_callbacks"] = sorted(current.get("sent_callbacks", set()))
            with SessionLocal() as db:
                row = db.get(BppLifecycleState, transaction_id)
                if row is None:
                    row = BppLifecycleState(transaction_id=transaction_id, state=durable)
                    db.add(row)
                else:
                    row.state = durable
                db.commit()
        except Exception as exc:  # never turn a callback into a 500 on local setup
            logger.warning("Durable BPP state write unavailable: %s", exc)

    def _refresh(self, transaction_id: str) -> Dict[str, Any]:
        state = self._load_durable(transaction_id)
        if state is not None:
            local_task = self._store.get(transaction_id, {}).get("lifecycle_task")
            local_rto_candidate = self._store.get(transaction_id, {}).get("rto_candidate", False)
            self._store[transaction_id] = state
            self._store[transaction_id]["lifecycle_task"] = local_task
            # This discriminator only exists for the short-lived request
            # window and must survive durable-state refreshes.
            self._store[transaction_id]["rto_candidate"] = local_rto_candidate
        return self._store[transaction_id]

    def get_or_create(self, transaction_id: str) -> Dict[str, Any]:
        if transaction_id not in self._store:
            self._store[transaction_id] = {
                "transaction_id": transaction_id,
                "current_state": "CREATED",
                "status_call_count": 0,
                "update_call_count": 0,
                "select_call_count": 0,
                "track_requested": False,
                "out_of_stock_flow": False,
                "rto_flow": False,
                "rto_candidate": False,
                "sent_callbacks": set(),
                "stored_order": None,
                "stored_context": None,
                "created_at": None,
                "order_id": None,
                "lifecycle_task": None,
                "cancelled": False,
            }
        return self._store[transaction_id]

    def set_lifecycle_task(self, transaction_id: str, task: Any) -> None:
        self.get_or_create(transaction_id)["lifecycle_task"] = task

    def cancel_lifecycle_task(self, transaction_id: str) -> bool:
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        session = self.get_or_create(transaction_id)
        session["cancelled"] = True
        self._persist_durable(transaction_id)
        task = session.get("lifecycle_task")
        if task and not task.done():
            task.cancel()
            logger.info(f"[LIFECYCLE TRACE] tx={transaction_id} cancelled pending lifecycle task")
            return True
        return False

    def is_cancelled(self, transaction_id: str) -> bool:
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        return bool(self.get_or_create(transaction_id).get("cancelled"))

    def store_order(self, transaction_id: str, order: Dict[str, Any], context: Dict[str, Any], created_at: str, order_id: str):
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        session = self.get_or_create(transaction_id)
        session["stored_order"] = order
        # Delayed callbacks can arrive with a sparse context. Preserve the
        # originating participant context instead of replacing it with that
        # incomplete callback request.
        stored_context = dict(session.get("stored_context") or {})
        stored_context.update({
            key: value
            for key, value in (context or {}).items()
            if value not in (None, "")
        })
        session["stored_context"] = stored_context
        session["created_at"] = created_at
        session["order_id"] = order_id
        self._persist_durable(transaction_id)
        logger.info(f"[LIFECYCLE TRACE] tx={transaction_id} stored order id={order_id}")

    def get_stored_order(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        return self.get_or_create(transaction_id).get("stored_order")

    def get_stored_context(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        return self.get_or_create(transaction_id).get("stored_context")

    def get_callback_context(
        self,
        transaction_id: str,
        fallback_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Recover the originating BAP context for delayed callbacks.

        The current request may contain only a transaction ID after the
        originating /confirm has completed. Stored values fill only missing
        data; current non-empty request fields remain authoritative for the
        current callback correlation.
        """
        merged = dict(self.get_stored_context(transaction_id) or {})
        merged.update({
            key: value
            for key, value in (fallback_context or {}).items()
            if value not in (None, "")
        })
        return merged

    def get_created_at(self, transaction_id: str) -> Optional[str]:
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        return self.get_or_create(transaction_id).get("created_at")

    def get_order_id(self, transaction_id: str) -> Optional[str]:
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        return self.get_or_create(transaction_id).get("order_id")

    def increment_select(self, transaction_id: str) -> int:
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        session = self.get_or_create(transaction_id)
        session["select_call_count"] += 1
        self._persist_durable(transaction_id)
        return session["select_call_count"]

    def get_select_count(self, transaction_id: str) -> int:
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        return self.get_or_create(transaction_id).get("select_call_count", 0)

    def mark_track_requested(self, transaction_id: str) -> None:
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        self.get_or_create(transaction_id)["track_requested"] = True
        self._persist_durable(transaction_id)

    def is_track_requested(self, transaction_id: str) -> bool:
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        return bool(self.get_or_create(transaction_id).get("track_requested"))

    def mark_issue_requested(self, transaction_id: str) -> int:
        """Count issue requests so the final feedback input stays input-only."""
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        state = self.get_or_create(transaction_id)
        count = int(state.get("issue_requests", 0)) + 1
        state["issue_requests"] = count
        self._persist_durable(transaction_id)
        return count

    def mark_out_of_stock_flow(self, transaction_id: str) -> None:
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        self.get_or_create(transaction_id)["out_of_stock_flow"] = True
        self._persist_durable(transaction_id)

    def mark_rto_flow(self, transaction_id: str) -> None:
        """Persist RTO classification across callbacks that omit RTO tags."""
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        self.get_or_create(transaction_id)["rto_flow"] = True
        self._persist_durable(transaction_id)

    def mark_rto_candidate(self, transaction_id: str) -> None:
        """Keep the short-lived ambiguous post-confirm branch open.

        Workbench's merchant RTO fixture does not include an RTO marker in
        select/init/confirm.  The next inbound /update is therefore the only
        reliable discriminator.  This flag is intentionally ephemeral and is
        not persisted as business state.
        """
        self.get_or_create(transaction_id)["rto_candidate"] = True

    def clear_rto_candidate(self, transaction_id: str) -> None:
        self.get_or_create(transaction_id)["rto_candidate"] = False

    def is_rto_candidate(self, transaction_id: str) -> bool:
        return bool(self.get_or_create(transaction_id).get("rto_candidate"))

    def is_rto_flow(self, transaction_id: str) -> bool:
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        return bool(self.get_or_create(transaction_id).get("rto_flow"))

    def is_out_of_stock_flow(self, transaction_id: str) -> bool:
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        return bool(self.get_or_create(transaction_id).get("out_of_stock_flow"))

    def advance_status_state(self, transaction_id: str, requested_state: Optional[str] = None) -> str:
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
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
        self._persist_durable(transaction_id)
        logger.info(f"[LIFECYCLE TRACE] tx={transaction_id} status_call={count} -> state={state}")
        return state

    def record_callback(self, transaction_id: str, action: str, state_code: Optional[str] = None):
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        session = self.get_or_create(transaction_id)
        key = f"{action}:{state_code}" if state_code else action
        session["sent_callbacks"].add(key)
        self._persist_durable(transaction_id)
        logger.info(f"[LIFECYCLE TRACE] tx={transaction_id} recorded callback: {key}")

    def has_callback(self, transaction_id: str, action: str, state_code: Optional[str] = None) -> bool:
        """Return whether a callback has already been reserved or sent."""
        self.get_or_create(transaction_id)
        self._refresh(transaction_id)
        key = f"{action}:{state_code}" if state_code else action
        return key in self.get_or_create(transaction_id)["sent_callbacks"]


lifecycle_tracker = LifecycleTracker()
