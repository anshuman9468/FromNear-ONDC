import json
import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.settings import settings
from app.ondc.accommodation.service import accommodation_buyer_service
from app.ondc.validators.protocol import validate_ondc_signature, validate_timestamp
from app.api.deps import get_async_db
from app.models.accommodation import AccommodationLedgerEvent
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter()


class AccommodationSearchRequest(BaseModel):
    location: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    guests: Optional[int] = Field(default=None, ge=1)
    rooms: Optional[int] = Field(default=None, ge=1)
    city: Optional[str] = None
    transaction_id: Optional[str] = None
    message_id: Optional[str] = None
    bpp_id: Optional[str] = None
    bpp_uri: Optional[str] = None
    tags: Optional[list[Dict[str, Any]]] = None


class AccommodationOrderActionRequest(BaseModel):
    transaction_id: str
    bpp_id: str
    bpp_uri: str
    order: Dict[str, Any]


class AccommodationOrderIdActionRequest(BaseModel):
    transaction_id: str
    bpp_id: str
    bpp_uri: str
    order_id: str
    message: Optional[Dict[str, Any]] = None


class AccommodationIssueRequest(AccommodationOrderIdActionRequest):
    issue: Dict[str, Any] = Field(default_factory=dict)


@router.get("/meta", status_code=status.HTTP_200_OK)
async def accommodation_meta() -> Dict[str, str]:
    profile = accommodation_buyer_service.profile
    return {
        "subscriber_id": profile.subscriber_id,
        "subscriber_uri": profile.subscriber_uri,
        "subscriber_url_path": profile.subscriber_uri.replace(
            f"https://{profile.subscriber_id}", "", 1
        ),
        "domain": profile.domain,
        "country": profile.country,
        "city": profile.city,
        "core_version": profile.version,
        "type": "BAP",
    }


@router.post("/search", status_code=status.HTTP_200_OK)
async def accommodation_search(request_data: AccommodationSearchRequest) -> Any:
    return await accommodation_buyer_service.initiate_search(
        location=request_data.location,
        check_in=request_data.check_in,
        check_out=request_data.check_out,
        guests=request_data.guests,
        rooms=request_data.rooms,
        city=request_data.city,
        transaction_id=request_data.transaction_id,
        message_id=request_data.message_id,
        bpp_id=request_data.bpp_id,
        bpp_uri=request_data.bpp_uri,
        tags=request_data.tags,
    )


@router.post("/select", status_code=status.HTTP_200_OK)
async def accommodation_select(request_data: AccommodationOrderActionRequest) -> Any:
    return await accommodation_buyer_service.send_order_action(
        action="select",
        transaction_id=request_data.transaction_id,
        bpp_id=request_data.bpp_id,
        bpp_uri=request_data.bpp_uri,
        order=request_data.order,
    )


@router.post("/init", status_code=status.HTTP_200_OK)
async def accommodation_init(request_data: AccommodationOrderActionRequest) -> Any:
    return await accommodation_buyer_service.send_order_action(
        action="init",
        transaction_id=request_data.transaction_id,
        bpp_id=request_data.bpp_id,
        bpp_uri=request_data.bpp_uri,
        order=request_data.order,
    )


@router.post("/confirm", status_code=status.HTTP_200_OK)
async def accommodation_confirm(request_data: AccommodationOrderActionRequest) -> Any:
    return await accommodation_buyer_service.send_order_action(
        action="confirm",
        transaction_id=request_data.transaction_id,
        bpp_id=request_data.bpp_id,
        bpp_uri=request_data.bpp_uri,
        order=request_data.order,
    )


@router.post("/status", status_code=status.HTTP_200_OK)
async def accommodation_status(request_data: AccommodationOrderIdActionRequest) -> Any:
    return await accommodation_buyer_service.send_order_id_action(
        action="status",
        transaction_id=request_data.transaction_id,
        bpp_id=request_data.bpp_id,
        bpp_uri=request_data.bpp_uri,
        order_id=request_data.order_id,
        extra_message=request_data.message,
    )


@router.post("/track", status_code=status.HTTP_200_OK)
async def accommodation_track(request_data: AccommodationOrderIdActionRequest) -> Any:
    return await accommodation_buyer_service.send_order_id_action(
        action="track",
        transaction_id=request_data.transaction_id,
        bpp_id=request_data.bpp_id,
        bpp_uri=request_data.bpp_uri,
        order_id=request_data.order_id,
        extra_message=request_data.message,
    )


@router.post("/cancel", status_code=status.HTTP_200_OK)
async def accommodation_cancel(request_data: AccommodationOrderIdActionRequest) -> Any:
    return await accommodation_buyer_service.send_order_id_action(
        action="cancel",
        transaction_id=request_data.transaction_id,
        bpp_id=request_data.bpp_id,
        bpp_uri=request_data.bpp_uri,
        order_id=request_data.order_id,
        extra_message=request_data.message,
    )


@router.post("/support", status_code=status.HTTP_200_OK)
async def accommodation_support(request_data: AccommodationOrderIdActionRequest) -> Any:
    return await accommodation_buyer_service.send_order_id_action(
        action="support",
        transaction_id=request_data.transaction_id,
        bpp_id=request_data.bpp_id,
        bpp_uri=request_data.bpp_uri,
        order_id=request_data.order_id,
        extra_message=request_data.message,
    )


@router.post("/issue", status_code=status.HTTP_200_OK)
async def accommodation_issue(request_data: AccommodationIssueRequest) -> Any:
    message = dict(request_data.message or {})
    message["issue"] = request_data.issue
    return await accommodation_buyer_service.send_order_id_action(
        action="issue", transaction_id=request_data.transaction_id,
        bpp_id=request_data.bpp_id, bpp_uri=request_data.bpp_uri,
        order_id=request_data.order_id, extra_message=message,
    )


@router.post("/update", status_code=status.HTTP_200_OK)
async def accommodation_update(request_data: AccommodationOrderActionRequest) -> Any:
    return await accommodation_buyer_service.send_order_action(
        action="update",
        transaction_id=request_data.transaction_id,
        bpp_id=request_data.bpp_id,
        bpp_uri=request_data.bpp_uri,
        order=request_data.order,
    )


async def process_accommodation_callback(request: Request, action: str, db: AsyncSession) -> Any:
    body_bytes = await request.body()
    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": {"ack": {"status": "NACK"}}, "error": {"message": "Invalid JSON"}},
        )

    context = payload.get("context", {})
    # Workbench unsolicited callbacks can omit standard context fields; return a
    # complete BAP context so the callback acknowledgement remains valid.
    context.setdefault("domain", settings.ACCOMMODATION_ONDC_DOMAIN)
    context.setdefault("country", "IND")
    context.setdefault("city", settings.ACCOMMODATION_ONDC_CITY)
    context.setdefault("core_version", settings.ACCOMMODATION_ONDC_VERSION)
    context.setdefault("version", settings.ACCOMMODATION_ONDC_VERSION)
    context.setdefault("bap_id", settings.ACCOMMODATION_ONDC_SUBSCRIBER_ID)
    context.setdefault("subscriber_id", settings.ACCOMMODATION_ONDC_SUBSCRIBER_ID)
    # Workbench's BAP callback validator uses the legacy camel-case spelling.
    context.setdefault("subscriberID", settings.ACCOMMODATION_ONDC_SUBSCRIBER_ID)
    context.setdefault("bap_uri", settings.ACCOMMODATION_ONDC_SUBSCRIBER_URI)
    context.setdefault("message_id", str(uuid.uuid4()))
    if context.get("action") and context["action"] != action:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Callback action mismatch: expected {action}, got {context['action']}",
        )

    timestamp_str = context.get("timestamp")
    if not timestamp_str:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "context": context,
                "message": {"ack": {"status": "NACK"}},
                "error": {"code": "10002", "message": "Missing 'timestamp' in context"},
            },
        )

    is_time_valid, time_err = validate_timestamp(timestamp_str)
    verify_signatures = settings.ACCOMMODATION_ONDC_VERIFY_SIGNATURES
    if not is_time_valid and verify_signatures:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "context": context,
                "message": {"ack": {"status": "NACK"}},
                "error": {"code": "10003", "message": time_err},
            },
        )

    if verify_signatures:
        is_sig_valid, sig_err = await validate_ondc_signature(request, body_bytes, context)
        if not is_sig_valid:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "context": context,
                    "message": {"ack": {"status": "NACK"}},
                    "error": {"code": "10001", "message": sig_err},
                },
            )

    await accommodation_buyer_service.handle_callback(payload, db)
    return {"context": context, "message": {"ack": {"status": "ACK"}}}


for callback_action in (
    "on_search",
    "on_select",
    "on_init",
    "on_confirm",
    "on_status",
    "on_track",
    "on_cancel",
    "on_support",
    "on_update",
    "on_issue",
    "on_issue_status",
):

    async def callback_endpoint(request: Request, db: AsyncSession = Depends(get_async_db), action: str = callback_action) -> Any:
        return await process_accommodation_callback(request, action, db)

    router.add_api_route(
        f"/ondc/{callback_action}",
        callback_endpoint,
        methods=["POST"],
        status_code=status.HTTP_200_OK,
        name=f"accommodation_{callback_action}",
    )


@router.get("/observability", status_code=status.HTTP_200_OK)
async def accommodation_observability(db: AsyncSession = Depends(get_async_db)) -> Dict[str, Any]:
    total = await db.scalar(select(func.count(AccommodationLedgerEvent.id)))
    inbound = await db.scalar(select(func.count(AccommodationLedgerEvent.id)).where(AccommodationLedgerEvent.direction == "inbound"))
    outbound = await db.scalar(select(func.count(AccommodationLedgerEvent.id)).where(AccommodationLedgerEvent.direction == "outbound"))
    actions = (await db.execute(select(AccommodationLedgerEvent.action, func.count(AccommodationLedgerEvent.id)).group_by(AccommodationLedgerEvent.action))).all()
    return {"service": "accommodation-bap", "events": total or 0, "inbound": inbound or 0, "outbound": outbound or 0, "by_action": dict(actions)}


@router.get("/reconciliation", status_code=status.HTTP_200_OK)
async def accommodation_reconciliation(db: AsyncSession = Depends(get_async_db)) -> Dict[str, Any]:
    rows = (await db.execute(select(AccommodationLedgerEvent).where(AccommodationLedgerEvent.direction == "inbound"))).scalars().all()
    confirmed = [row for row in rows if row.action in {"on_confirm", "on_status"} and row.amount is not None]
    total = sum(row.amount or 0 for row in confirmed)
    return {"service": "accommodation-bap", "orders_observed": len({row.order_id for row in rows if row.order_id}), "settlement_events": len(confirmed), "settlement_amount": round(total, 2), "currency": "INR", "status": "ready"}
