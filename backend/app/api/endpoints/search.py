from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api.deps import get_async_db
from app.ondc.services.search import ondc_search_service
from app.ondc.schemas.product import ProductModel

router = APIRouter()


from typing import Optional

class SearchRequest(BaseModel):
    query: Optional[str] = ""
    transaction_id: Optional[str] = None
    bpp_id: Optional[str] = None
    bpp_uri: Optional[str] = None
    mode: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


@router.post(
    "",
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Bad Request - Invalid parameters or protocol validation failed"},
        401: {"description": "Unauthorized - Missing or invalid signing keys/configuration"},
        404: {"description": "Not Found - Registry lookup failed"},
        502: {"description": "Bad Gateway - ONDC Gateway unreachable or DNS resolution failed"},
        503: {"description": "Service Unavailable - ONDC network error"},
    }
)
async def initiate_search(
    request_data: SearchRequest,
) -> Any:
    """Initiate and broadcast an ONDC search request to the ONDC gateway or BPP."""
    result = await ondc_search_service.initiate_search(
        query=(request_data.query or "").strip(),
        transaction_id=request_data.transaction_id,
        bpp_id=request_data.bpp_id,
        bpp_uri=request_data.bpp_uri,
        mode=request_data.mode,
        start_time=request_data.start_time,
        end_time=request_data.end_time,
    )
    return result


@router.get("/results", response_model=List[ProductModel])
async def get_search_results(
    transaction_id: str,
    db: AsyncSession = Depends(get_async_db)
) -> Any:
    """Retrieve internal mapped catalog results for a given search transaction ID."""
    transaction_id = transaction_id.strip()
    if not transaction_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parameter 'transaction_id' is required",
        )
        
    results = await ondc_search_service.get_results(db, transaction_id)
    return results
