"""Auto-grading engine — weighted grade from diagnostic inputs.

Weights: Battery 25%, Parts 20%, Crashes 20%, Cosmetic 20%, Locks 15%
Grade mapping: A=4, B=3, C=2, D=1
"""

from typing import Optional

from app.models.crash import CrashAnalysis
from app.models.diagnostic import DiagnosticResult
from app.models.grading import ComponentGrade, DeviceGrade
from app.models.verification import VerificationResult

WEIGHTS = {
    "battery": 0.25,
    "parts": 0.20,
    "crashes": 0.20,
    "cosmetic": 0.20,
    "locks": 0.15,
}

GRADE_SCORES = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0}


def _score_to_grade(score: float) -> str:
    if score >= 3.5:
        return "A"
    if score >= 2.5:
        return "B"
    if score >= 1.5:
        return "C"
    return "D"


def _grade_to_color(grade: str) -> str:
    return {"A": "green", "B": "green", "C": "yellow", "D": "red"}.get(grade, "gray")


def grade_battery(health_percent: float) -> ComponentGrade:
    if health_percent >= 90:
        g, detail = "A", f"{health_percent}% — excellent"
    elif health_percent >= 80:
        g, detail = "B", f"{health_percent}% — good"
    elif health_percent >= 70:
        g, detail = "C", f"{health_percent}% — fair"
    else:
        g, detail = "D", f"{health_percent}% — poor"
    return ComponentGrade(
        component="battery", grade=g, score=GRADE_SCORES[g],
        weight=WEIGHTS["battery"], details=detail,
    )


def grade_parts(all_original: bool, replaced_count: int = 0) -> ComponentGrade:
    if all_original:
        g, detail = "A", "All parts original"
    elif replaced_count == 1:
        g, detail = "B", "1 part replaced"
    elif replaced_count >= 2:
        g, detail = "C", f"{replaced_count} parts replaced"
    else:
        g, detail = "B", "Parts status unclear"
    return ComponentGrade(
        component="parts", grade=g, score=GRADE_SCORES[g],
        weight=WEIGHTS["parts"], details=detail,
    )


def grade_crashes(analysis: CrashAnalysis) -> ComponentGrade:
    total = analysis.total_reports
    has_critical = analysis.max_severity >= 5
    has_hardware = analysis.max_severity >= 4

    if total <= 2 and not has_critical:
        g, detail = "A", f"{total} minor crashes"
    elif total <= 10 and not has_critical:
        g, detail = "B", f"{total} crashes, no critical"
    elif total <= 30 or (has_critical and not has_hardware):
        g, detail = "C", f"{total} crashes, severity {analysis.max_severity}"
    else:
        g, detail = "D", f"{total} crashes, hardware-level severity"
    return ComponentGrade(
        component="crashes", grade=g, score=GRADE_SCORES[g],
        weight=WEIGHTS["crashes"], details=detail,
    )


def grade_cosmetic(grade_letter: Optional[str] = None) -> Optional[ComponentGrade]:
    """Returns None if cosmetic grade hasn't been entered yet."""
    if grade_letter is None:
        return None
    g = grade_letter.upper()
    if g not in GRADE_SCORES:
        return None
    labels = {"A": "No damage", "B": "Light scratches", "C": "Cracks/dents", "D": "Major damage"}
    return ComponentGrade(
        component="cosmetic", grade=g, score=GRADE_SCORES[g],
        weight=WEIGHTS["cosmetic"], details=labels.get(g, ""),
    )


def grade_locks(verification: VerificationResult) -> ComponentGrade:
    if verification.fmi_status.lower() == "on":
        g, detail = "D", "Find My iPhone ON (iCloud locked)"
    elif verification.mdm_enrolled:
        g, detail = "C", f"MDM enrolled: {verification.mdm_organization}"
    elif verification.carrier_locked:
        g, detail = "B", f"Carrier locked: {verification.carrier}"
    else:
        g, detail = "A", "Clean — unlocked, no MDM, FMI off"
    return ComponentGrade(
        component="locks", grade=g, score=GRADE_SCORES[g],
        weight=WEIGHTS["locks"], details=detail,
    )


def calculate_grade(
    diagnostics: DiagnosticResult,
    crash_analysis: CrashAnalysis,
    verification: VerificationResult,
    cosmetic_grade: Optional[str] = None,
) -> DeviceGrade:
    """Calculate overall device grade from all inputs."""
    components: list[ComponentGrade] = [
        grade_battery(diagnostics.battery.health_percent),
        grade_parts(diagnostics.parts.all_original, len(diagnostics.parts.replaced_parts)),
        grade_crashes(crash_analysis),
        grade_locks(verification),
    ]

    cosmetic = grade_cosmetic(cosmetic_grade)
    is_partial = cosmetic is None
    if cosmetic:
        components.append(cosmetic)

    # Weighted average over available components
    total_weight = sum(c.weight for c in components)
    if total_weight > 0:
        weighted_sum = sum(c.score * c.weight for c in components)
        overall_score = weighted_sum / total_weight
    else:
        overall_score = 0.0

    overall_grade = _score_to_grade(overall_score)

    return DeviceGrade(
        overall_grade=overall_grade,
        overall_score=round(overall_score, 2),
        components=components,
        is_partial=is_partial,
        color=_grade_to_color(overall_grade),
    )
