"""Hardware diagnostics — battery, parts originality, storage.

Uses pymobiledevice3 DiagnosticsService and MobileGestalt.
"""

import logging
from typing import Any, Optional

from app.models.diagnostic import BatteryInfo, DiagnosticResult, PartsOriginality, StorageInfo

logger = logging.getLogger(__name__)


def run_diagnostics(udid: Optional[str] = None) -> DiagnosticResult:
    """Run full hardware diagnostics on a connected device."""
    battery = _get_battery(udid)
    parts = _get_parts_originality(udid)
    storage = _get_storage(udid)
    raw: dict[str, Any] = {}

    return DiagnosticResult(battery=battery, parts=parts, storage=storage, raw=raw)


def _get_battery(udid: Optional[str] = None) -> BatteryInfo:
    try:
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.services.diagnostics import DiagnosticsService

        with create_using_usbmux(serial=udid) as lockdown:
            with DiagnosticsService(lockdown) as diag:
                bat = diag.get_battery()

                nominal = bat.get("NominalChargeCapacity", 0)
                design = bat.get("DesignCapacity", 1)
                health = round((nominal / design) * 100, 1) if design > 0 else 0.0

                return BatteryInfo(
                    health_percent=health,
                    cycle_count=bat.get("CycleCount", 0),
                    design_capacity=design,
                    nominal_capacity=nominal,
                    current_capacity=bat.get("AppleRawCurrentCapacity", 0),
                    temperature=bat.get("Temperature", 0) / 100,
                    voltage=bat.get("Voltage", 0),
                    is_charging=bat.get("IsCharging", False),
                    fully_charged=bat.get("FullyCharged", False),
                )
    except Exception as e:
        logger.error("Battery diagnostics failed: %s", e)
        return BatteryInfo()


def _get_parts_originality(udid: Optional[str] = None) -> PartsOriginality:
    try:
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.services.diagnostics import DiagnosticsService

        gestalt_keys = [
            "BatteryIsOriginal",
            "a/ScreenIsOriginal",
        ]

        with create_using_usbmux(serial=udid) as lockdown:
            with DiagnosticsService(lockdown) as diag:
                try:
                    result = diag.mobilegestalt(keys=gestalt_keys)
                    gestalt = result.get("MobileGestalt", {})
                except Exception:
                    # MobileGestalt deprecated on iOS 17.4+
                    logger.warning("MobileGestalt unavailable, parts check skipped")
                    return PartsOriginality()

                replaced = []
                battery_orig = gestalt.get("BatteryIsOriginal")
                screen_orig = gestalt.get("a/ScreenIsOriginal")

                if battery_orig is False:
                    replaced.append("battery")
                if screen_orig is False:
                    replaced.append("screen")

                return PartsOriginality(
                    battery_original=battery_orig,
                    screen_original=screen_orig,
                    replaced_parts=replaced,
                    all_original=len(replaced) == 0,
                )
    except Exception as e:
        logger.error("Parts originality check failed: %s", e)
        return PartsOriginality()


def _get_storage(udid: Optional[str] = None) -> StorageInfo:
    try:
        from pymobiledevice3.lockdown import create_using_usbmux

        with create_using_usbmux(serial=udid) as lockdown:
            disk = lockdown.get_value(domain="com.apple.disk_usage", key=None)
            if disk:
                total = disk.get("TotalDataCapacity", 0)
                available = disk.get("TotalDataAvailable", 0)
                total_gb = round(total / (1024**3), 1)
                available_gb = round(available / (1024**3), 1)
                return StorageInfo(
                    total_gb=total_gb,
                    used_gb=round(total_gb - available_gb, 1),
                    available_gb=available_gb,
                )
    except Exception as e:
        logger.error("Storage check failed: %s", e)
    return StorageInfo()
