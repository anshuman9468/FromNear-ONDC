import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from .config import settings
from .protocol import CALLBACK_ACTIONS, action_payload, search_payload
from .transport import dispatch

logger = logging.getLogger("ride-hailing-bap")
app = FastAPI(title="FromNear Ride Hailing BAP", version="0.1.0",
              description="Isolated ONDC:TRV10 Buyer NP service for FromNear.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://fromnear.com", "https://www.fromnear.com", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


class SearchRequest(BaseModel):
    start_gps: str = Field(min_length=3)
    end_gps: str = Field(min_length=3)
    city: str = "std:080"


class ActionRequest(BaseModel):
    transaction_id: str
    bpp_id: str
    bpp_uri: str
    message: dict[str, Any]
    city: str = "std:080"


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "fromnear-ride-hailing-bap", "domain": settings.domain,
            "subscriber_id": settings.subscriber_id, "subscriber_uri": settings.subscriber_uri}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ride-hailing-bap"}


@app.get("/meta")
async def meta() -> dict[str, str]:
    return {"subscriber_id": settings.subscriber_id, "subscriber_uri": settings.subscriber_uri,
            "domain": settings.domain, "role": "BAP", "version": settings.version}


@app.get("/static-terms.txt", response_class=PlainTextResponse)
async def static_terms() -> str:
    return "FromNear TRV10 Buyer NP terms: buyer finder fee and settlement terms are supplied in each ONDC request."


@app.post("/search")
async def search(request: SearchRequest) -> dict[str, Any]:
    payload = search_payload(start_gps=request.start_gps, end_gps=request.end_gps, city=request.city)
    return {"request": payload, "ack": await dispatch(payload)}


async def callback(request: Request, action: str) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc
    received = payload.get("context")
    if not isinstance(received, dict):
        return JSONResponse(status_code=400, content={"message": {"ack": {"status": "NACK"}},
                                                       "error": {"message": "Missing context"}})
    if received.get("domain") != settings.domain or received.get("action") != action:
        return JSONResponse(status_code=400, content={"message": {"ack": {"status": "NACK"}}, "error": {"message": "Invalid callback context"}})
    logger.info("TRV10 callback action=%s transaction_id=%s", action, received.get("transaction_id"))
    return JSONResponse(content={"message": {"ack": {"status": "ACK"}}})


for callback_action in CALLBACK_ACTIONS:
    async def endpoint(request: Request, action: str = callback_action) -> JSONResponse:
        return await callback(request, action)
    app.add_api_route(f"/{callback_action}", endpoint, methods=["POST"], name=callback_action)


# Keep this catch-all after the callback routes so /on_search, /on_confirm, etc.
# are always handled as inbound callbacks rather than action requests.
@app.post("/{action}")
async def order_action(action: str, request: ActionRequest) -> dict[str, Any]:
    payload = action_payload(action, transaction_id=request.transaction_id, bpp_id=request.bpp_id,
                             bpp_uri=request.bpp_uri, message=request.message, city=request.city)
    return {"request": payload, "ack": await dispatch(payload)}
