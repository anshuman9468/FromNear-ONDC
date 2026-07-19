import time
import logging
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from app.core.logging import correlation_id_ctx

logger = logging.getLogger("app.middleware.request_logging")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        
        # Retrieve correlation ID from request headers or generate a new one
        correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get("x-correlation-id")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
            
        # Token set for correlation ID context variable
        token = correlation_id_ctx.set(correlation_id)
        
        method = request.method
        path = request.url.path
        query_params = dict(request.query_params)
        
        # Log request receipt
        logger.info(
            f"HTTP Request: {method} {path}",
            extra={
                "method": method,
                "path": path,
                "query_params": query_params,
                "client": request.client.host if request.client else "unknown",
            },
        )
        
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Set header on response
            response.headers["X-Correlation-ID"] = correlation_id
            
            # Log successful completion
            logger.info(
                f"HTTP Response: {method} {path} - Status {response.status_code} - Taken {duration:.4f}s",
                extra={
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "duration_seconds": duration,
                },
            )
            return response
        except Exception as e:
            duration = time.time() - start_time
            # Log errors/exceptions
            logger.error(
                f"HTTP Request Failure: {method} {path} - Error: {str(e)} - Taken {duration:.4f}s",
                exc_info=True,
                extra={
                    "method": method,
                    "path": path,
                    "duration_seconds": duration,
                },
            )
            raise e
        finally:
            # Reset context variable to prevent leakage
            correlation_id_ctx.reset(token)
