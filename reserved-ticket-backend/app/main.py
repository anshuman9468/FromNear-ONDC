import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the isolated TRV12 buyer service."""

    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")

    ONDC_SUBSCRIBER_ID: str
    ONDC_SUBSCRIBER_URI: str
    ONDC_DOMAIN: str = "ONDC:TRV12"
    ONDC_TYPE: str = "BAP"
    ONDC_COUNTRY: str = "IND"
    ONDC_CITY: str = "*"
    ONDC_CORE_VERSION: str = "2.0.0"


settings = Settings()

app = FastAPI(
    title="FromNear Reserved Ticket Booking BAP",
    description="Isolated ONDC Reserved Ticket Booking (ONDC:TRV12) backend.",
    version="0.1.0",
)


def context_for_callback(received_context: dict[str, Any], action: str) -> dict[str, Any]:
    """Build the mandatory ACK context without trusting omitted mock fields."""
    context = dict(received_context)
    context.update(
        {
            "domain": context.get("domain", settings.ONDC_DOMAIN),
            "country": context.get("country", settings.ONDC_COUNTRY),
            "city": context.get("city", settings.ONDC_CITY),
            "bap_id": settings.ONDC_SUBSCRIBER_ID,
            "bap_uri": settings.ONDC_SUBSCRIBER_URI,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "message_id": context.get("message_id", str(uuid4())),
        }
    )
    return context


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "fromnear-reserved-ticket-bap",
        "domain": settings.ONDC_DOMAIN,
        "subscriber_id": settings.ONDC_SUBSCRIBER_ID,
        "subscriber_uri": settings.ONDC_SUBSCRIBER_URI,
    }


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "reserved-ticket-bap"}


@app.get("/on_subscribe")
async def on_subscribe() -> dict[str, str]:
    """Expose the registered public key after ONDC key registration is configured."""
    public_key = os.getenv("ONDC_SIGNING_PUBLIC_KEY")
    if not public_key:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"error": "ONDC public key is not configured"})
    return {"signing_public_key": public_key}


async def callback(request: Request, action: str) -> JSONResponse:
    """Receive ONDC callbacks; transaction processing is added per certified TRV12 flow."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": {"ack": {"status": "NACK"}}, "error": {"message": "Invalid JSON"}},
        )

    context = payload.get("context")
    if not isinstance(context, dict):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": {"ack": {"status": "NACK"}}, "error": {"message": "Missing context"}},
        )

    return JSONResponse(content={"context": context_for_callback(context, action), "message": {"ack": {"status": "ACK"}}})


for callback_action in (
    "on_search", "on_select", "on_init", "on_confirm", "on_status",
    "on_track", "on_cancel", "on_update", "on_support", "on_issue", "on_issue_status",
):
    async def endpoint(request: Request, action: str = callback_action) -> JSONResponse:
        return await callback(request, action)

    app.add_api_route(f"/{callback_action}", endpoint, methods=["POST"], name=callback_action)
