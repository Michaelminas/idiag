"""Crash report analysis models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CrashPattern(BaseModel):
    """A single crash signature pattern from crash_patterns.json."""

    pattern: str
    subsystem: str
    severity: int  # 1-5
    description: str


class CrashMatch(BaseModel):
    """A crash report matched against a known pattern."""

    filename: str = ""
    process: str = ""
    exception: str = ""
    subsystem: str = ""
    severity: int = 0
    description: str = ""
    timestamp: Optional[datetime] = None


class CrashAnalysis(BaseModel):
    """Aggregated crash analysis for a device."""

    total_reports: int = 0
    matched_reports: int = 0
    unmatched_reports: int = 0
    matches: list[CrashMatch] = []
    subsystem_counts: dict[str, int] = {}
    max_severity: int = 0
    risk_score: float = 0.0  # 0-100
    summary: str = ""
