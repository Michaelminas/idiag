"""Diagnostics and crash analysis API routes."""

from fastapi import APIRouter

from app.models.crash import CrashAnalysis
from app.models.diagnostic import DiagnosticResult
from app.models.grading import DeviceGrade
from app.models.verification import VerificationResult
from app.services import diagnostic_engine, log_analyzer, verification_service
from app.services.grading_engine import calculate_grade

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("/run")
@router.get("/run/{udid}")
def run_diagnostics(udid: str | None = None) -> DiagnosticResult:
    """Run hardware diagnostics (battery, parts, storage)."""
    return diagnostic_engine.run_diagnostics(udid)


@router.get("/crashes")
@router.get("/crashes/{udid}")
def analyze_crashes(udid: str | None = None) -> CrashAnalysis:
    """Pull and analyze crash reports from device."""
    return log_analyzer.analyze_device(udid)


@router.get("/grade/{udid}")
async def calculate_device_grade(
    udid: str,
    imei: str = "",
    cosmetic: str | None = None,
) -> DeviceGrade:
    """Run all diagnostics and compute the overall device grade."""
    diag = diagnostic_engine.run_diagnostics(udid)
    crashes = log_analyzer.analyze_device(udid)
    verif = await verification_service.run_verification(udid=udid, imei=imei)
    return calculate_grade(diag, crashes, verif, cosmetic)
