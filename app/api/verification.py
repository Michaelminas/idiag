"""Verification API routes."""

from fastapi import APIRouter

from app.models.verification import VerificationResult
from app.services import verification_service

router = APIRouter(prefix="/api/verification", tags=["verification"])


@router.get("/check/{imei}")
async def check_imei(imei: str, udid: str | None = None) -> VerificationResult:
    """Run IMEI verification checks (SICKW + local)."""
    return await verification_service.run_verification(udid=udid, imei=imei)
