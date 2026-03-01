"""Diagnostics API routes."""

from fastapi import APIRouter, HTTPException

from app.models.diagnostic import DiagnosticResult
from app.services import diagnostic_engine

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("/run")
@router.get("/run/{udid}")
def run_diagnostics(udid: str | None = None) -> DiagnosticResult:
    """Run full hardware diagnostics on connected device."""
    result = diagnostic_engine.run_diagnostics(udid)
    return result
