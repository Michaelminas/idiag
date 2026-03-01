"""Hardware diagnostics — battery, parts originality, storage.

Uses pymobiledevice3 DiagnosticsService and MobileGestalt.
Shares a single lockdown session for all checks.
"""

import logging
from typing import Any, Optional

from app.models.diagnostic import BatteryInfo, DiagnosticResult, PartsOriginality, StorageInfo

logger = logging.getLogger(__name__)


def run_diagnostics(udid: Optional[str] = None) -> DiagnosticResult:
    """Run full hardware diagnostics on a connected device.

    Opens a single USB lockdown session and reuses it for all checks.
    """
    try:
        from pymobiledevice3.lockdown import create_using_usbmux

        with create_using_usbmux(serial=udid) as lockdown:
            battery = _get_battery(lockdown)
            parts = _get_parts_originality(lockdown)
            storage = _get_storage(lockdown)
            return DiagnosticResult(battery=battery, parts=parts, storage=storage, raw={})
    except ImportError:
        logger.error("pymobiledevice3 not installed")
        return DiagnosticResult()
    except Exception as e:
        logger.error("Device connection failed: %s", e)
        return DiagnosticResult()


def _normalize_temperature(raw_temp: int | float) -> float:
    """Normalize temperature to degrees Celsius.

    Apple's IORegistry reports in centi-degrees (e.g. 2850 = 28.5°C),
    but some pymobiledevice3 versions already normalize to degrees.
    """
    if raw_temp > 100:
        return round(raw_temp / 100, 1)
    return round(raw_temp, 1)


def _get_battery(lockdown: Any) -> BatteryInfo:
    try:
        from pymobiledevice3.services.diagnostics import DiagnosticsService

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
                temperature=_normalize_temperature(bat.get("Temperature", 0)),
                voltage=bat.get("Voltage", 0),
                is_charging=bat.get("IsCharging", False),
                fully_charged=bat.get("FullyCharged", False),
            )
    except Exception as e:
        logger.error("Battery diagnostics failed: %s", e)
        return BatteryInfo()


def _get_parts_originality(lockdown: Any) -> PartsOriginality:
    try:
        from pymobiledevice3.services.diagnostics import DiagnosticsService

        gestalt_keys = [
            "BatteryIsOriginal",
            "a/ScreenIsOriginal",
        ]

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


def _get_storage(lockdown: Any) -> StorageInfo:
    try:
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
