"""Diagnostics and crash analysis API routes."""

import asyncio
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.models.crash import CrashAnalysis
from app.models.diagnostic import DiagnosticResult
from app.models.grading import DeviceGrade
from app.models.verification import VerificationResult
from app.services import diagnostic_engine, log_analyzer, verification_service
from app.services.grading_engine import calculate_grade

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("/run")
@router.get("/run/{udid}")
async def run_diagnostics(udid: str | None = None) -> DiagnosticResult:
    """Run hardware diagnostics (battery, parts, storage)."""
    return await asyncio.to_thread(diagnostic_engine.run_diagnostics, udid)


@router.get("/crashes")
@router.get("/crashes/{udid}")
async def analyze_crashes(udid: str | None = None) -> CrashAnalysis:
    """Pull and analyze crash reports from device."""
    return await asyncio.to_thread(log_analyzer.analyze_device, udid)


class GradeRequest(BaseModel):
    """Pre-computed diagnostic results for grading."""
    diagnostics: DiagnosticResult
    crashes: CrashAnalysis
    verification: VerificationResult
    cosmetic: Optional[str] = None


@router.post("/grade")
def calculate_device_grade(req: GradeRequest) -> DeviceGrade:
    """Compute overall device grade from pre-computed diagnostic results."""
    return calculate_grade(req.diagnostics, req.crashes, req.verification, req.cosmetic)


@router.get("/grade/{udid}")
async def calculate_device_grade_live(
    udid: str,
    imei: str = "",
    cosmetic: str | None = None,
) -> DeviceGrade:
    """Run all diagnostics from scratch and compute the overall device grade."""
    diag = await asyncio.to_thread(diagnostic_engine.run_diagnostics, udid)
    crashes = await asyncio.to_thread(log_analyzer.analyze_device, udid)
    verif = await verification_service.run_verification(udid=udid, imei=imei)
    return calculate_grade(diag, crashes, verif, cosmetic)
