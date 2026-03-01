"""Device grading models."""

from typing import Optional

from pydantic import BaseModel


class ComponentGrade(BaseModel):
    """Grade for a single component."""

    component: str
    grade: str  # A, B, C, D
    score: float  # 4.0, 3.0, 2.0, 1.0
    weight: float
    details: str = ""


class DeviceGrade(BaseModel):
    """Overall device grade computed from component grades."""

    overall_grade: str = ""  # A, B, C, D
    overall_score: float = 0.0  # weighted average (1.0-4.0)
    components: list[ComponentGrade] = []
    is_partial: bool = True  # True until cosmetic is entered
    color: str = "gray"  # green, yellow, red, gray
