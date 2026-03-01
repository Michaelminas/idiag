"""Diagnostics and crash analysis API routes."""

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.inventory import get_db
from app.models.crash import CrashAnalysis
from app.models.diagnostic import DiagnosticResult
from app.models.grading import DeviceGrade
from app.models.inventory import DeviceSnapshot
from app.models.verification import VerificationResult
from app.services import device_service, diagnostic_engine, log_analyzer, verification_service
from app.services.grading_engine import calculate_grade

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


def _get_crash_history(udid: str) -> list[dict[str, int]]:
    """Build subsystem_counts history from stored crash reports for a device."""
    db = get_db()
    device = db.get_device_by_udid(udid)
    if not device or not device.id:
        return []
    rows = db.list_crash_history(device.id)
    if not rows:
        return []
    # Group by timestamp to reconstruct per-scan subsystem counts
    scans: dict[str, dict[str, int]] = {}
    for row in rows:
        ts = row.get("timestamp", "")
        subsystem = row.get("subsystem", "")
        count = row.get("count", 1)
        if ts not in scans:
            scans[ts] = {}
        scans[ts][subsystem] = scans[ts].get(subsystem, 0) + count
    # Return sorted by timestamp (oldest first)
    return [scans[ts] for ts in sorted(scans.keys())]


@router.get("/run")
@router.get("/run/{udid}")
async def run_diagnostics(udid: str | None = None) -> DiagnosticResult:
    """Run hardware diagnostics (battery, parts, storage)."""
    return await asyncio.to_thread(diagnostic_engine.run_diagnostics, udid)


@router.get("/crashes")
@router.get("/crashes/{udid}")
async def analyze_crashes(udid: str | None = None) -> CrashAnalysis:
    """Pull and analyze crash reports from device."""
    history = _get_crash_history(udid) if udid else []
    return await asyncio.to_thread(log_analyzer.analyze_device, udid, history)


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
    history = _get_crash_history(udid)
    crashes = await asyncio.to_thread(log_analyzer.analyze_device, udid, history)
    verif = await verification_service.run_verification(udid=udid, imei=imei)
    return calculate_grade(diag, crashes, verif, cosmetic)


@router.get("/snapshot/{udid}")
async def get_device_snapshot(udid: str, cosmetic: str | None = None) -> DeviceSnapshot:
    """Run all diagnostics and assemble a full device snapshot."""
    info = await asyncio.to_thread(device_service.get_device_info, udid)
    if not info:
        raise HTTPException(status_code=404, detail="Device not found or connection failed")

    diag = await asyncio.to_thread(diagnostic_engine.run_diagnostics, udid)
    history = _get_crash_history(udid)
    crashes = await asyncio.to_thread(log_analyzer.analyze_device, udid, history)

    verif = None
    if info.imei:
        verif = await verification_service.run_verification(udid=udid, imei=info.imei)

    grade = calculate_grade(
        diag, crashes, verif or VerificationResult(), cosmetic
    )

    return DeviceSnapshot(
        info=info,
        diagnostics=diag,
        crash_analysis=crashes,
        verification=verif,
        grade=grade,
    )
