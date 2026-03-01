"""Crash log analysis engine — pull reports and match against patterns.

Pulls crash reports via pymobiledevice3 CrashReportsManager,
then matches against patterns in crash_patterns.json.
"""

import json
import logging
import re
import tempfile
from pathlib import Path
from typing import Optional

from app.config import settings
from app.models.crash import CrashAnalysis, CrashMatch, CrashPattern

logger = logging.getLogger(__name__)


def _load_patterns() -> list[CrashPattern]:
    path = settings.crash_patterns_path
    if not path.exists():
        return []
    with open(path) as f:
        raw = json.load(f)
    return [CrashPattern(**p) for p in raw]


try:
    PATTERNS = _load_patterns()
except Exception:
    logger.error("Failed to load crash patterns, using empty list")
    PATTERNS = []


def analyze_crash_text(text: str, filename: str = "") -> Optional[CrashMatch]:
    """Match a single crash report's text against known patterns."""
    for pattern in PATTERNS:
        if re.search(pattern.pattern, text, re.IGNORECASE):
            return CrashMatch(
                filename=filename,
                subsystem=pattern.subsystem,
                severity=pattern.severity,
                description=pattern.description,
            )
    return None


def analyze_device(udid: Optional[str] = None) -> CrashAnalysis:
    """Pull all crash reports from a device and analyze them."""
    result = CrashAnalysis()

    tmpdir_handle = None
    try:
        crash_files, tmpdir_handle = _pull_crash_reports(udid)
    except Exception as e:
        logger.error("Failed to pull crash reports: %s", e)
        result.summary = f"Failed to pull crash reports: {e}"
        return result

    matches: list[CrashMatch] = []
    subsystem_counts: dict[str, int] = {}
    max_severity = 0

    try:
        for filepath in crash_files:
            result.total_reports += 1
            try:
                text = filepath.read_text(errors="replace")
            except Exception:
                continue

            match = analyze_crash_text(text, filepath.name)
            if match:
                matches.append(match)
                result.matched_reports += 1
                subsystem_counts[match.subsystem] = subsystem_counts.get(match.subsystem, 0) + 1
                max_severity = max(max_severity, match.severity)
            else:
                result.unmatched_reports += 1
    finally:
        if tmpdir_handle:
            tmpdir_handle.cleanup()

    result.matches = matches
    result.subsystem_counts = subsystem_counts
    result.max_severity = max_severity
    result.risk_score = _calculate_risk_score(matches, result.total_reports)
    result.summary = _generate_summary(result)

    return result


def _pull_crash_reports(udid: Optional[str] = None) -> tuple[list[Path], tempfile.TemporaryDirectory]:
    """Pull crash reports from device to a temp directory.

    Returns (file_list, tmpdir_handle). Caller must keep tmpdir_handle alive
    while reading files, then call tmpdir_handle.cleanup().
    """
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.crash_reports import CrashReportsManager

    tmpdir = tempfile.TemporaryDirectory(prefix="idiag_crashes_")
    tmppath = Path(tmpdir.name)

    with create_using_usbmux(serial=udid) as lockdown:
        with CrashReportsManager(lockdown) as mgr:
            mgr.pull(out=str(tmppath))

    # Collect all .ips and .crash files
    files = list(tmppath.rglob("*.ips")) + list(tmppath.rglob("*.crash"))
    return files, tmpdir


def _calculate_risk_score(matches: list[CrashMatch], total: int) -> float:
    """0-100 risk score based on severity and frequency."""
    if not matches:
        return 0.0
    severity_sum = sum(m.severity for m in matches)
    # Weight by severity and count
    score = min(100.0, (severity_sum / max(total, 1)) * 20)
    return round(score, 1)


def _generate_summary(analysis: CrashAnalysis) -> str:
    if analysis.total_reports == 0:
        return "No crash reports found on device."
    if analysis.matched_reports == 0:
        return f"{analysis.total_reports} crash reports found, none matched known hardware patterns."

    parts = [f"{analysis.total_reports} crash reports analyzed."]
    for subsystem, count in sorted(
        analysis.subsystem_counts.items(), key=lambda x: -x[1]
    ):
        parts.append(f"{subsystem}: {count} reports")

    if analysis.max_severity >= 5:
        parts.append("CRITICAL hardware-level crashes detected.")
    elif analysis.max_severity >= 4:
        parts.append("Significant hardware-related crashes detected.")

    return " ".join(parts)
