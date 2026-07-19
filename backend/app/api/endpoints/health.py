from typing import Any, Dict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.sql import text

from app.api.deps import get_db

router = APIRouter()


@router.get("", response_model=Dict[str, Any])
def health_check(db: Session = Depends(get_db)) -> Any:
    """Check the health status of the application and database connectivity."""
    db_status = "healthy"
    try:
        # Perform a simple query to verify db connectivity
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "service": "ONDC Buyer Certification Core",
    }
