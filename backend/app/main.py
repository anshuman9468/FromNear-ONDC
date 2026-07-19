from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.api import api_router
from app.core.config import settings
from app.logging.config import setup_logging
from app.middleware.logging import RequestLoggingMiddleware
from app.ondc.exceptions import (
    SigningConfigurationError,
    GatewayConnectionError,
    RegistryLookupError,
    ProtocolValidationError,
)
import logging

# Configure logging at application startup
setup_logging()
logger = logging.getLogger(__name__)

def validate_ondc_config() -> None:
    """Validate mandatory ONDC settings at startup to fail fast."""
    mandatory = {
        "ONDC_GATEWAY_URL": settings.ONDC_GATEWAY_URL,
        "ONDC_REGISTRY_URL": settings.ONDC_REGISTRY_URL,
        "ONDC_SUBSCRIBER_ID": settings.ONDC_SUBSCRIBER_ID,
        "ONDC_SUBSCRIBER_URI": settings.ONDC_SUBSCRIBER_URI,
        "ONDC_UNIQUE_KEY_ID": settings.ONDC_UNIQUE_KEY_ID,
    }
    missing = [k for k, v in mandatory.items() if not v or v.strip() == "" or "placeholder" in str(v).lower()]
    if missing:
        error_msg = f"ONDC Configuration Error: Mandatory configuration fields are missing or unset: {', '.join(missing)}"
        logger.critical(error_msg)
        raise ValueError(error_msg)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend foundation and database management service for ONDC Buyer Certification using Pramaan",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# CORS Configuration
# Adjust origins in production as necessary
origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:3000",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Startup event handler
@app.on_event("startup")
def startup_event():
    validate_ondc_config()

# Exception Handlers
@app.exception_handler(SigningConfigurationError)
async def signing_configuration_exception_handler(request: Request, exc: SigningConfigurationError):
    return JSONResponse(
        status_code=401,
        content={
            "error": "ONDC signing key not configured",
            "reason": "Ed25519 private key missing",
            "action": "Configure ONDC_SIGNING_PRIVATE_KEY"
        }
    )

@app.exception_handler(GatewayConnectionError)
async def gateway_connection_exception_handler(request: Request, exc: GatewayConnectionError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "gateway": exc.gateway,
            "reason": exc.reason
        }
    )

@app.exception_handler(RegistryLookupError)
async def registry_lookup_exception_handler(request: Request, exc: RegistryLookupError):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Registry lookup failed",
            "reason": str(exc)
        }
    )

@app.exception_handler(ProtocolValidationError)
async def protocol_validation_exception_handler(request: Request, exc: ProtocolValidationError):
    return JSONResponse(
        status_code=400,
        content={
            "error": "Invalid request",
            "reason": str(exc)
        }
    )

# API Router inclusion
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def read_root():
    """Welcome endpoint for root navigation checking."""
    return {
        "message": f"Welcome to the {settings.PROJECT_NAME} API.",
        "docs_url": "/docs",
        "health_check": f"{settings.API_V1_STR}/health",
    }

