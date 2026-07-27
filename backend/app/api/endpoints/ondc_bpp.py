import json
import logging
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.core.settings import settings
from app.ondc.validators.protocol import validate_timestamp, validate_ondc_signature
from app.ondc.bpp.services.search import bpp_search_service
from app.ondc.bpp.services.select import bpp_select_service
from app.ondc.bpp.services.init import bpp_init_service
from app.ondc.bpp.services.confirm import bpp_confirm_service
from app.ondc.bpp.services.status import bpp_status_service
from app.ondc.bpp.services.update import bpp_update_service

logger = logging.getLogger(__name__)
router = APIRouter()


async def process_incoming_bpp_request(request: Request, action: str, handler_func):
    """Generic helper to parse, validate, and dispatch incoming ONDC BPP requests."""
    body_bytes = await request.body()

    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        logger.error(f"Request body for {action} is not valid JSON")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": {"ack": {"status": "NACK"}}, "error": {"code": "10000", "message": "Request body must be valid JSON"}}
        )

    context = payload.get("context", {})
    timestamp_str = context.get("timestamp")
    if not timestamp_str:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": {"ack": {"status": "NACK"}}, "error": {"code": "10002", "message": "Missing 'timestamp' in context"}}
        )

    is_time_valid, time_err = validate_timestamp(timestamp_str)
    if not is_time_valid:
        logger.warning(f"Timestamp validation failed for {action}: {time_err}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": {"ack": {"status": "NACK"}}, "error": {"code": "10003", "message": f"Timestamp validation failed: {time_err}"}}
        )

    if settings.ONDC_VERIFY_SIGNATURES:
        is_sig_valid, sig_err = await validate_ondc_signature(request, body_bytes, context)
        if not is_sig_valid:
            logger.warning(f"Signature validation failed for {action}: {sig_err}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"message": {"ack": {"status": "NACK"}}, "error": {"code": "10001", "message": f"Signature verification failed: {sig_err}"}}
            )

    try:
        await handler_func(payload)
    except Exception as e:
        logger.error(f"Failed to process {action} payload: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": {"ack": {"status": "NACK"}}, "error": {"code": "50000", "message": f"Failed to handle request: {str(e)}"}}
        )

    return {"message": {"ack": {"status": "ACK"}}}


@router.post("/search", status_code=status.HTTP_200_OK)
async def search_endpoint(request: Request):
    """BPP: Receive /search from Gateway/BAP and respond with on_search."""
    return await process_incoming_bpp_request(request, "search", bpp_search_service.handle_search)


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


@router.post("/update", status_code=status.HTTP_200_OK)
async def update_endpoint(request: Request):
    """BPP: Receive /update (return request) from BAP and respond with on_update + lifecycle pushes."""
    return await process_incoming_bpp_request(request, "update", bpp_update_service.handle_update)
