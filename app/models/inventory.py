"""Inventory-related models."""

from typing import Optional

from pydantic import BaseModel

from app.models.crash import CrashAnalysis
from app.models.device import DeviceInfo, DeviceRecord
from app.models.diagnostic import DiagnosticResult
from app.models.grading import DeviceGrade
from app.models.verification import VerificationResult


class DeviceSnapshot(BaseModel):
    """Complete point-in-time snapshot of a device — used by the dashboard."""

    info: DeviceInfo
    diagnostics: Optional[DiagnosticResult] = None
    verification: Optional[VerificationResult] = None
    crash_analysis: Optional[CrashAnalysis] = None
    grade: Optional[DeviceGrade] = None
    record: Optional[DeviceRecord] = None


class SerialDecoded(BaseModel):
    """Result of local serial number decoding."""

    raw: str
    is_randomized: bool = False
    factory: str = ""
    year_candidates: list[int] = []
    half: str = ""
    week_in_half: Optional[int] = None
    week_of_year: Optional[int] = None
    model_code: str = ""


class IMEIValidation(BaseModel):
    """Result of IMEI Luhn validation."""

    raw: str
    is_valid: bool = False
    tac: str = ""
    luhn_valid: bool = False
    notes: list[str] = []


class FraudCheck(BaseModel):
    """Cross-reference fraud detection result."""

    is_suspicious: bool = False
    flags: list[str] = []
    fraud_score: int = 0  # 0-100 weighted score
    randomized_note: str = ""  # note about randomized serial
