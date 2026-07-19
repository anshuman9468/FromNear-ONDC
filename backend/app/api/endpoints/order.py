import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any, Optional

from app.api.deps import get_async_db, get_current_user_async
from app.models.user import User
from app.schemas.order import (
    OrderSchema,
    SelectRequestSchema,
    InitRequestSchema,
    ConfirmRequestSchema,
    CancelRequestSchema,
    SupportRequestSchema,
)
from app.ondc.services.select import select_service
from app.ondc.services.init import init_service
from app.ondc.services.confirm import confirm_service
from app.ondc.services.status import status_service
from app.ondc.services.track import track_service
from app.ondc.services.cancel import cancel_service
from app.ondc.services.support import support_service
from app.repositories.order import order_repo
from app.ondc.exceptions import ONDCError

logger = logging.getLogger(__name__)
router = APIRouter()

ONDC_SWAGGER_RESPONSES = {
    400: {"description": "Bad Request - Invalid parameters or protocol validation failed"},
    401: {"description": "Unauthorized - Missing or invalid signing keys/configuration"},
    404: {"description": "Not Found - Registry lookup failed or Order not found"},
    502: {"description": "Bad Gateway - ONDC Gateway/BPP unreachable or DNS resolution failed"},
    503: {"description": "Service Unavailable - ONDC network error"},
}


async def get_optional_current_user(
    db: AsyncSession = Depends(get_async_db),
    user_or_none: Optional[User] = Depends(lambda: None)  # Will try to resolve manually if needed
) -> User:
    """Helper dependency that returns authenticated user or falls back to a default system user (ID=1) for testing."""
    # For ONDC Pramaan certification / sandbox, auth might be skipped or mocked.
    # We fallback to user_id=1 to guarantee seamless sandbox executions.
    try:
        # We can try to authenticate the user
        user = await get_current_user_async(db)
        return user
    except Exception:
        # Fallback to system default user (ID 1)
        # Verify if a user exists
        from sqlalchemy import select
        from app.models.user import User as UserModel
        result = await db.execute(select(UserModel).filter(UserModel.id == 1))
        user = result.scalars().first()
        if not user:
            # If no user at ID 1, create a temporary system user for flow execution
            user = UserModel(id=1, email="system@ondc.cert", hashed_password="mock", full_name="ONDC System User", is_active=True)
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return user


@router.post("/select", status_code=status.HTTP_200_OK, responses=ONDC_SWAGGER_RESPONSES)
async def select_items(
    request_data: SelectRequestSchema,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_optional_current_user),
) -> Any:
    """Initiate ONDC select flow to obtain quotes from BPP."""
    try:
        result = await select_service.initiate_select(
            db=db,
            transaction_id=request_data.transaction_id,
            bpp_id=request_data.bpp_id,
            bpp_uri=request_data.bpp_uri,
            provider_id=request_data.provider_id,
            provider_name=request_data.provider_name,
            items=request_data.items,
            user_id=current_user.id,
        )
        return result
    except ONDCError as e:
        raise e
    except Exception as e:
        logger.error(f"Select request failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Select failed: {str(e)}"
        )


@router.post("/init", status_code=status.HTTP_200_OK, responses=ONDC_SWAGGER_RESPONSES)
async def init_order(
    request_data: InitRequestSchema,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_optional_current_user),
) -> Any:
    """Initiate ONDC init flow to specify shipping/billing address and details."""
    try:
        result = await init_service.initiate_init(
            db=db,
            transaction_id=request_data.transaction_id,
            billing_address=request_data.billing_address.model_dump(),
            shipping_address=request_data.shipping_address.model_dump(),
            user_id=current_user.id,
        )
        return result
    except ONDCError as e:
        raise e
    except Exception as e:
        logger.error(f"Init request failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Init failed: {str(e)}"
        )


@router.post("/confirm", status_code=status.HTTP_200_OK, responses=ONDC_SWAGGER_RESPONSES)
async def confirm_order(
    request_data: ConfirmRequestSchema,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_optional_current_user),
) -> Any:
    """Initiate ONDC confirm flow to finalize order with payments."""
    try:
        result = await confirm_service.initiate_confirm(
            db=db,
            transaction_id=request_data.transaction_id,
        )
        return result
    except ONDCError as e:
        raise e
    except Exception as e:
        logger.error(f"Confirm request failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Confirm failed: {str(e)}"
        )


@router.get("/status", status_code=status.HTTP_200_OK, responses=ONDC_SWAGGER_RESPONSES)
async def get_order_status(
    transaction_id: str = Query(..., description="Transaction ID of the order"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_optional_current_user),
) -> Any:
    """Query current ONDC order status from BPP and return DB representation."""
    try:
        # Trigger ONDC network call
        await status_service.initiate_status(db=db, transaction_id=transaction_id)
        
        # Return current order state from DB
        order = await order_repo.get_by_transaction_id_async(db, transaction_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order not found for transaction_id={transaction_id}"
            )
        return OrderSchema.model_validate(order)
    except HTTPException:
        raise
    except ONDCError as e:
        raise e
    except Exception as e:
        logger.error(f"Status request failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Status query failed: {str(e)}"
        )


@router.get("/track", status_code=status.HTTP_200_OK, responses=ONDC_SWAGGER_RESPONSES)
async def track_order(
    transaction_id: str = Query(..., description="Transaction ID of the order"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_optional_current_user),
) -> Any:
    """Query order tracking url from BPP and return DB representation."""
    try:
        # Trigger ONDC network call
        await track_service.initiate_track(db=db, transaction_id=transaction_id)
        
        # Return current order state from DB
        order = await order_repo.get_by_transaction_id_async(db, transaction_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order not found for transaction_id={transaction_id}"
            )
        return OrderSchema.model_validate(order)
    except HTTPException:
        raise
    except ONDCError as e:
        raise e
    except Exception as e:
        logger.error(f"Track request failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Track failed: {str(e)}"
        )


@router.post("/cancel", status_code=status.HTTP_200_OK, responses=ONDC_SWAGGER_RESPONSES)
async def cancel_order(
    request_data: CancelRequestSchema,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_optional_current_user),
) -> Any:
    """Initiate order cancellation flow."""
    try:
        result = await cancel_service.initiate_cancel(
            db=db,
            transaction_id=request_data.transaction_id,
            cancellation_reason_id=request_data.cancellation_reason_id,
        )
        return result
    except ONDCError as e:
        raise e
    except Exception as e:
        logger.error(f"Cancel request failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cancel failed: {str(e)}"
        )


@router.post("/support", status_code=status.HTTP_200_OK, responses=ONDC_SWAGGER_RESPONSES)
async def support_request(
    request_data: SupportRequestSchema,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_optional_current_user),
) -> Any:
    """Initiate customer support inquiry for order."""
    try:
        result = await support_service.initiate_support(
            db=db,
            transaction_id=request_data.transaction_id,
        )
        return result
    except ONDCError as e:
        raise e
    except Exception as e:
        logger.error(f"Support request failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Support failed: {str(e)}"
        )


@router.get("/orders", response_model=List[OrderSchema], status_code=status.HTTP_200_OK)
async def list_orders(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_optional_current_user),
) -> List[OrderSchema]:
    """List orders created in the database."""
    orders = await order_repo.get_multi_orders_async(db, skip=skip, limit=limit)
    return [OrderSchema.model_validate(o) for o in orders]


@router.get("/orders/{transaction_id}", response_model=OrderSchema, status_code=status.HTTP_200_OK)
async def get_order_by_transaction_id(
    transaction_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_optional_current_user),
) -> OrderSchema:
    """Retrieve details of a single order by transaction ID."""
    order = await order_repo.get_by_transaction_id_async(db, transaction_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order not found for transaction_id={transaction_id}"
        )
    return OrderSchema.model_validate(order)
