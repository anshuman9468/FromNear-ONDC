from fastapi import APIRouter
from app.api.endpoints import auth, health, search, ondc, ondc_bpp, order, diagnostics

api_router = APIRouter()

# Include routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(ondc.router, prefix="/ondc", tags=["ONDC Protocol (BAP)"])
api_router.include_router(ondc_bpp.router, prefix="/ondc", tags=["ONDC Protocol (BPP)"])
api_router.include_router(diagnostics.router, prefix="/diagnostics", tags=["Diagnostics"])
api_router.include_router(order.router, prefix="", tags=["Order Operations"])
