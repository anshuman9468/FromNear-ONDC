import json
import logging
import asyncio
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from app.api.deps import get_async_db
from app.core.settings import settings
from app.core.database import AsyncSessionLocal
from app.ondc.services.search import ondc_search_service
from app.ondc.services.select import select_service
from app.ondc.services.init import init_service
from app.ondc.services.confirm import confirm_service
from app.ondc.services.status import status_service
from app.ondc.services.track import track_service
from app.ondc.services.cancel import cancel_service
from app.ondc.services.support import support_service
from app.ondc.services.update import update_service
from app.ondc.services.issue import issue_service
from app.ondc.validators.protocol import validate_timestamp, validate_ondc_signature

logger = logging.getLogger(__name__)
router = APIRouter()


async def process_ondc_callback(
    request: Request,
    db: AsyncSession,
    action: str,
    handler_func
) -> Any:
    """Generic helper to parse, validate signatures, validate timestamps, and handle ONDC callback payloads."""
    body_bytes = await request.body()
    
    # 1. Unconditionally log every inbound callback body
    try:
        body_str = body_bytes.decode('utf-8', errors='ignore')
        logger.info(f"UNCONDITIONAL INCOMING CALLBACK [{action}]: {body_str}")
    except Exception as e:
        logger.error(f"Failed to decode incoming callback body for {action}: {e}")

    context = {}
    
    try:
        payload = json.loads(body_bytes)
        context = payload.get("context", {})
        if context.get("city") == "*":
            context["city"] = settings.ONDC_CITY
    except json.JSONDecodeError:
        logger.error(f"Request body for {action} is not valid JSON")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "context": context,
                "message": {"ack": {"status": "NACK"}},
                "error": {
                    "code": "10000",
                    "message": "Request body must be valid JSON"
                }
            }
        )
        
    timestamp_str = context.get("timestamp")
    if not timestamp_str:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "context": context,
                "message": {"ack": {"status": "NACK"}},
                "error": {
                    "code": "10002",
                    "message": "Missing 'timestamp' in context"
                }
            }
        )
        
    is_time_valid, time_err = validate_timestamp(timestamp_str)
    if not is_time_valid:
        logger.warning(f"ONDC timestamp validation failed for {action}: {time_err}")
        # Only block with 400 Bad Request if signature verification is enabled
        if settings.ONDC_VERIFY_SIGNATURES:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "context": context,
                    "message": {"ack": {"status": "NACK"}},
                    "error": {
                        "code": "10003",
                        "message": f"Timestamp validation failed: {time_err}"
                    }
                }
            )
        
    if settings.ONDC_VERIFY_SIGNATURES:
        is_sig_valid, sig_err = await validate_ondc_signature(request, body_bytes, context)
        if not is_sig_valid:
            logger.warning(f"ONDC signature validation failed for {action}: {sig_err}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "context": context,
                    "message": {"ack": {"status": "NACK"}},
                    "error": {
                        "code": "10001",
                        "message": f"Signature verification failed: {sig_err}"
                    }
                }
            )
            
    # 2. Fire-and-forget background processing of the callback logic
    async def run_handler_async():
        async with AsyncSessionLocal() as local_db:
            try:
                await handler_func(local_db, payload)
                logger.info(f"Successfully processed background callback for action: {action}")
            except Exception as e:
                logger.error(f"Failed to process background {action} payload: {str(e)}", exc_info=True)

    asyncio.create_task(run_handler_async())
        
    return {
        "context": context,
        "message": {"ack": {"status": "ACK"}}
    }


@router.post("/on_search", status_code=status.HTTP_200_OK)
async def on_search_callback(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """Callback endpoint for BPPs to submit catalog search results."""
    return await process_ondc_callback(request, db, "on_search", ondc_search_service.handle_on_search)


@router.post("/on_select", status_code=status.HTTP_200_OK)
async def on_select_callback(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """Callback endpoint for BPPs to submit item selection quote details."""
    return await process_ondc_callback(request, db, "on_select", select_service.handle_on_select)


@router.post("/on_init", status_code=status.HTTP_200_OK)
async def on_init_callback(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """Callback endpoint for BPPs to submit order initialization details."""
    return await process_ondc_callback(request, db, "on_init", init_service.handle_on_init)


@router.post("/on_confirm", status_code=status.HTTP_200_OK)
async def on_confirm_callback(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """Callback endpoint for BPPs to submit order confirmation details."""
    return await process_ondc_callback(request, db, "on_confirm", confirm_service.handle_on_confirm)


@router.post("/on_status", status_code=status.HTTP_200_OK)
async def on_status_callback(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """Callback endpoint for BPPs to submit order status update details."""
    return await process_ondc_callback(request, db, "on_status", status_service.handle_on_status)


@router.post("/on_track", status_code=status.HTTP_200_OK)
async def on_track_callback(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """Callback endpoint for BPPs to submit order tracking details."""
    return await process_ondc_callback(request, db, "on_track", track_service.handle_on_track)


@router.post("/on_cancel", status_code=status.HTTP_200_OK)
async def on_cancel_callback(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """Callback endpoint for BPPs to submit order cancellation details."""
    return await process_ondc_callback(request, db, "on_cancel", cancel_service.handle_on_cancel)


@router.post("/on_support", status_code=status.HTTP_200_OK)
async def on_support_callback(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """Callback endpoint for BPPs to submit customer support details."""
    return await process_ondc_callback(request, db, "on_support", support_service.handle_on_support)


@router.post("/on_update", status_code=status.HTTP_200_OK)
async def on_update_callback(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """Callback endpoint for BPPs to submit order update details."""
    return await process_ondc_callback(request, db, "on_update", update_service.handle_on_update)


@router.post("/on_issue", status_code=status.HTTP_200_OK)
async def on_issue_callback(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """Callback endpoint for BPPs to submit issue creation details."""
    return await process_ondc_callback(request, db, "on_issue", issue_service.handle_on_issue)


@router.post("/on_issue_status", status_code=status.HTTP_200_OK)
async def on_issue_status_callback(
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """Callback endpoint for BPPs to submit issue status update details."""
    return await process_ondc_callback(request, db, "on_issue_status", issue_service.handle_on_issue_status)
