"""Diagnostic result models."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class BatteryInfo(BaseModel):
    """Battery diagnostic data from IORegistry."""

    health_percent: float = 0.0
    cycle_count: int = 0
    design_capacity: int = 0  # mAh
    nominal_capacity: int = 0  # mAh (current max)
    current_capacity: int = 0  # mAh (right now)
    temperature: float = 0.0  # Celsius
    voltage: int = 0  # mV
    is_charging: bool = False
    fully_charged: bool = False


class PartsOriginality(BaseModel):
    """Non-original parts detection via MobileGestalt."""

    battery_original: Optional[bool] = None
    screen_original: Optional[bool] = None
    camera_original: Optional[bool] = None
    replaced_parts: list[str] = []
    all_original: bool = True


class StorageInfo(BaseModel):
    """Device storage stats."""

    total_gb: float = 0.0
    used_gb: float = 0.0
    available_gb: float = 0.0


class DiagnosticResult(BaseModel):
    """Full diagnostic snapshot for a device."""

    id: Optional[int] = None
    device_id: Optional[int] = None
    timestamp: Optional[datetime] = None
    battery: BatteryInfo = BatteryInfo()
    parts: PartsOriginality = PartsOriginality()
    storage: StorageInfo = StorageInfo()
    raw: dict[str, Any] = {}
