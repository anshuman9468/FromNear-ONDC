from typing import Any, Dict
from fastapi import APIRouter

from app.ondc.services.diagnostics import run_diagnostics

router = APIRouter()

@router.get("/ondc", response_model=Dict[str, Any])
async def ondc_diagnostics() -> Any:
    """Run comprehensive ONDC validation checks and return a diagnostic report."""
    report = await run_diagnostics()
    return report
