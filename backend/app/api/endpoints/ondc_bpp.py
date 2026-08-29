import json
import logging
import asyncio
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.core.settings import settings
from app.ondc.validators.protocol import validate_timestamp, validate_ondc_signature
from app.ondc.bpp.services.search import bpp_search_service
from app.ondc.bpp.services.select import bpp_select_service
from app.ondc.bpp.services.init import bpp_init_service
from app.ondc.bpp.services.confirm import bpp_confirm_service
from app.ondc.bpp.services.status import bpp_status_service
from app.ondc.bpp.services.track import bpp_track_service
from app.ondc.bpp.services.update import bpp_update_service
from app.ondc.bpp.services.cancel import bpp_cancel_service
from app.ondc.bpp.services.issue import bpp_issue_service
from app.ondc.bpp.state_machine import lifecycle_tracker

logger = logging.getLogger(__name__)
router = APIRouter()


def _bpp_lookup_keys():
    """Return BPP public keys in the array shape expected by Workbench."""
    return [
        {
            "signing_public_key": settings.ONDC_BPP_SIGNING_PUBLIC_KEY or settings.ONDC_SIGNING_PUBLIC_KEY,
            "encr_public_key": settings.ONDC_BPP_ENC_PUBLIC_KEY or settings.ONDC_ENC_PUBLIC_KEY,
        }
    ]


async def _run_bpp_handler_after_ack(action: str, payload: dict, handler_func):
    """Run callback work after Workbench has recorded the inbound request."""
    try:
        # Workbench persists the inbound request asynchronously after its ACK;
        # keep enough separation to avoid an on_* callback arriving first.
        await asyncio.sleep(2.5)
        await handler_func(payload)
    except Exception as e:
        logger.error(f"Failed to process {action} payload after ACK: {str(e)}", exc_info=True)


async def process_incoming_bpp_request(request: Request, action: str, handler_func):
    """Generic helper to parse, validate, and dispatch incoming ONDC BPP requests."""
    body_bytes = await request.body()
    context = {}

    try:
        payload = json.loads(body_bytes)
        context = payload.get("context", {})
    except json.JSONDecodeError:
        logger.error(f"Request body for {action} is not valid JSON")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"context": context, "message": {"ack": {"status": "NACK"}}, "error": {"code": "10000", "message": "Request body must be valid JSON"}}
        )

    timestamp_str = context.get("timestamp")
    if not timestamp_str:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"context": context, "message": {"ack": {"status": "NACK"}}, "error": {"code": "10002", "message": "Missing 'timestamp' in context"}}
        )

    is_time_valid, time_err = validate_timestamp(timestamp_str)
    if not is_time_valid:
        logger.warning(f"Timestamp validation failed for {action}: {time_err}")
        # Only hard-reject on timestamp mismatch when signature verification is active
        if settings.ONDC_VERIFY_SIGNATURES:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"context": context, "message": {"ack": {"status": "NACK"}}, "error": {"code": "10003", "message": f"Timestamp validation failed: {time_err}"}}
            )

    if settings.ONDC_VERIFY_SIGNATURES:
        is_sig_valid, sig_err = await validate_ondc_signature(request, body_bytes, context)
        if not is_sig_valid:
            logger.warning(f"Signature validation failed for {action}: {sig_err}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"context": context, "message": {"ack": {"status": "NACK"}}, "error": {"code": "10001", "message": f"Signature verification failed: {sig_err}"}}
            )

    order_id = payload.get("message", {}).get("order", {}).get("id", "UNKNOWN")
    if action == "track":
        # Mark the request before the delayed handler starts so a concurrent
        # post-confirm task cannot emit a status after Workbench enters track.
        lifecycle_tracker.mark_track_requested(context.get("transaction_id", "default_tx"))
    if action == "issue":
        # The IGM scenario sends a second issue as final feedback. It must be
        # acknowledged as input without repeating the initial issue callbacks.
        lifecycle_tracker.mark_issue_requested(context.get("transaction_id", "default_tx"))
    logger.info(
        f"\n=== LIFECYCLE TRACE INBOUND ===\n"
        f"Timestamp: {context.get('timestamp')}\n"
        f"Action: {action}\n"
        f"Transaction ID: {context.get('transaction_id')}\n"
        f"Message ID: {context.get('message_id')}\n"
        f"Order ID: {order_id}\n"
        f"Request URL: {request.url}\n"
        f"HTTP Method: {request.method}\n"
        f"Caller: Workbench/BAP\n"
    )

    # Return the ACK first so Workbench records the inbound request before
    # receiving its direct callback. The handler is then scheduled after the
    # response to preserve ONDC callback ordering.
    asyncio.create_task(_run_bpp_handler_after_ack(action, payload, handler_func))

    return {"context": context, "message": {"ack": {"status": "ACK"}}}


async def _acknowledge_catalog_rejection(_: dict) -> None:
    """Catalog rejection is informational and does not require a callback."""
    return None


@router.get("/lookup", status_code=status.HTTP_200_OK)
async def lookup_get_endpoint():
    """BPP subscriber key lookup for Workbench/registry signature validation."""
    return _bpp_lookup_keys()


@router.post("/lookup", status_code=status.HTTP_200_OK)
async def lookup_post_endpoint():
    """BPP subscriber key lookup for Workbench/registry signature validation."""
    return _bpp_lookup_keys()


@router.post("/search", status_code=status.HTTP_200_OK)
async def search_endpoint(request: Request):
    """BPP: Receive /search from Gateway/BAP and respond with on_search."""
    return await process_incoming_bpp_request(request, "search", bpp_search_service.handle_search)


@router.post("/catalog_rejection", status_code=status.HTTP_200_OK)
async def catalog_rejection_endpoint(request: Request):
    """Accept Workbench catalog-rejection notifications instead of returning 404."""
    return await process_incoming_bpp_request(
        request, "catalog_rejection", _acknowledge_catalog_rejection
    )


@router.post("/select", status_code=status.HTTP_200_OK)
async def select_endpoint(request: Request):
    """BPP: Receive /select from BAP and respond with on_select quote."""
    return await process_incoming_bpp_request(request, "select", bpp_select_service.handle_select)


@router.post("/init", status_code=status.HTTP_200_OK)
async def init_endpoint(request: Request):
    """BPP: Receive /init from BAP and respond with on_init payment terms."""
    return await process_incoming_bpp_request(request, "init", bpp_init_service.handle_init)


@router.post("/confirm", status_code=status.HTTP_200_OK)
async def confirm_endpoint(request: Request):
    """BPP: Receive /confirm from BAP and respond with on_confirm + lifecycle on_status updates."""
    return await process_incoming_bpp_request(request, "confirm", bpp_confirm_service.handle_confirm)


@router.post("/status", status_code=status.HTTP_200_OK)
async def status_endpoint(request: Request):
    """BPP: Receive /status from BAP and respond with on_status."""
    return await process_incoming_bpp_request(request, "status", bpp_status_service.handle_status)


@router.post("/track", status_code=status.HTTP_200_OK)
async def track_endpoint(request: Request):
    """BPP: Receive /track from BAP and respond with on_track."""
    return await process_incoming_bpp_request(request, "track", bpp_track_service.handle_track)


@router.post("/issue", status_code=status.HTTP_200_OK)
async def issue_endpoint(request: Request):
    """BPP: Receive /issue from BAP and respond with IGM callbacks."""
    return await process_incoming_bpp_request(request, "issue", bpp_issue_service.handle_issue)


@router.post("/update", status_code=status.HTTP_200_OK)
async def update_endpoint(request: Request):
    """BPP: Receive /update (return request) from BAP and respond with on_update + lifecycle pushes."""
    return await process_incoming_bpp_request(request, "update", bpp_update_service.handle_update)


@router.post("/cancel", status_code=status.HTTP_200_OK)
async def cancel_endpoint(request: Request):
    """BPP: Receive /cancel from BAP and respond with on_cancel."""
    return await process_incoming_bpp_request(request, "cancel", bpp_cancel_service.handle_cancel)
