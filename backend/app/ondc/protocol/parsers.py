from typing import Dict, Any, List, Optional


class BaseResponseParser:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self.payload = payload
        self.context = payload.get("context", {})
        self.message = payload.get("message", {})
        self.error = payload.get("error")

    @property
    def is_success(self) -> bool:
        return self.error is None

    @property
    def transaction_id(self) -> str:
        return self.context.get("transaction_id", "")

    @property
    def message_id(self) -> str:
        return self.context.get("message_id", "")

    @property
    def bpp_id(self) -> str:
        return self.context.get("bpp_id", "")

    @property
    def bpp_uri(self) -> str:
        return self.context.get("bpp_uri", "")


class SearchResponse(BaseResponseParser):
    @property
    def catalog_providers(self) -> List[Dict[str, Any]]:
        catalog = self.message.get("catalog", {})
        return catalog.get("bpp/providers", []) or catalog.get("providers", [])


class SelectResponse(BaseResponseParser):
    @property
    def quote_price(self) -> float:
        try:
            return float(self.message.get("order", {}).get("quote", {}).get("price", {}).get("value", 0.0))
        except (ValueError, TypeError):
            return 0.0

    @property
    def provider_id(self) -> str:
        return self.message.get("order", {}).get("provider", {}).get("id", "")

    @property
    def items(self) -> List[Dict[str, Any]]:
        return self.message.get("order", {}).get("items", [])


class InitResponse(BaseResponseParser):
    @property
    def quote_price(self) -> float:
        try:
            return float(self.message.get("order", {}).get("quote", {}).get("price", {}).get("value", 0.0))
        except (ValueError, TypeError):
            return 0.0

    @property
    def payment_terms(self) -> Dict[str, Any]:
        return self.message.get("order", {}).get("payment", {})


class ConfirmResponse(BaseResponseParser):
    @property
    def order_id(self) -> str:
        return self.message.get("order", {}).get("id", "")

    @property
    def state(self) -> str:
        return self.message.get("order", {}).get("state", "")

    @property
    def total_amount(self) -> float:
        try:
            return float(self.message.get("order", {}).get("payment", {}).get("params", {}).get("amount", 0.0))
        except (ValueError, TypeError):
            try:
                return float(self.message.get("order", {}).get("quote", {}).get("price", {}).get("value", 0.0))
            except (ValueError, TypeError):
                return 0.0


class StatusResponse(BaseResponseParser):
    @property
    def order_id(self) -> str:
        return self.message.get("order", {}).get("id", "")

    @property
    def state(self) -> str:
        return self.message.get("order", {}).get("state", "")


class TrackResponse(BaseResponseParser):
    @property
    def tracking_url(self) -> str:
        return self.message.get("tracking", {}).get("url", "")

    @property
    def status(self) -> str:
        return self.message.get("tracking", {}).get("status", "")


class CancelResponse(BaseResponseParser):
    @property
    def order_id(self) -> str:
        return self.message.get("order", {}).get("id", "")

    @property
    def state(self) -> str:
        return self.message.get("order", {}).get("state", "")


class SupportResponse(BaseResponseParser):
    @property
    def phone(self) -> str:
        return self.message.get("phone", "")

    @property
    def email(self) -> str:
        return self.message.get("email", "")

    @property
    def uri(self) -> str:
        return self.message.get("uri", "")


class UpdateResponse(BaseResponseParser):
    @property
    def order_id(self) -> str:
        return self.message.get("order", {}).get("id", "")

    @property
    def state(self) -> str:
        return self.message.get("order", {}).get("state", "")
