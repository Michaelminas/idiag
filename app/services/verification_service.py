"""Verification service — SICKW API + local activation check.

SICKW API (service 61): iPhone Carrier + FMI + Blacklist bundle.
Local: pymobiledevice3 ActivationState + MDM profile detection.
"""

import logging
from typing import Optional

import httpx

from app.config import settings
from app.models.verification import VerificationResult

logger = logging.getLogger(__name__)


async def check_imei_sickw(imei: str) -> dict:
    """Call SICKW API for carrier/FMI/blacklist bundle check.

    Returns the parsed result dict, or error dict on failure.
    """
    if not settings.sickw_api_key:
        return {"error": "SICKW API key not configured"}

    params = {
        "format": "beta",
        "key": settings.sickw_api_key,
        "imei": imei,
        "service": str(settings.sickw_default_service),
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(settings.sickw_base_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        result = data.get("result", "")
        if isinstance(result, str) and result in (
            "Invalid Key", "Invalid IMEI or SN", "Insufficient balance", "Service not found", ""
        ):
            return {"error": f"SICKW API error: {result}"}

        return data
    except Exception as e:
        logger.error("SICKW API call failed: %s", e)
        return {"error": str(e)}


def _parse_sickw_result(raw: dict) -> VerificationResult:
    """Parse SICKW beta format response into VerificationResult."""
    result_data = raw.get("result", {})
    if not isinstance(result_data, dict):
        return VerificationResult(raw=raw)

    # Normalize field values
    blacklist = result_data.get("Blacklist Status", "unknown").strip().lower()
    fmi = result_data.get("iCloud Lock", result_data.get("Find My iPhone", "unknown"))
    carrier = result_data.get("Carrier", "")
    sim_lock = result_data.get("SIM-Lock Status", "")
    carrier_locked = sim_lock.strip().lower() == "locked"

    return VerificationResult(
        blacklist_status="clean" if "clean" in blacklist else ("blacklisted" if "black" in blacklist else blacklist),
        fmi_status=fmi.strip().lower() if isinstance(fmi, str) else "unknown",
        carrier=carrier,
        carrier_locked=carrier_locked,
        sim_lock_status=sim_lock,
        raw=raw,
    )


def check_activation_local(udid: Optional[str] = None) -> str:
    """Check ActivationState locally via pymobiledevice3."""
    try:
        from pymobiledevice3.lockdown import create_using_usbmux

        with create_using_usbmux(serial=udid) as lockdown:
            state = lockdown.get_value(key="ActivationState")
            return state or "unknown"
    except Exception as e:
        logger.error("Local activation check failed: %s", e)
        return "unknown"


def check_mdm_local(udid: Optional[str] = None) -> tuple[bool, str]:
    """Check MDM enrollment locally. Returns (is_enrolled, organization)."""
    try:
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.services.mobile_config import MobileConfigService

        with create_using_usbmux(serial=udid) as lockdown:
            with MobileConfigService(lockdown) as cfg:
                cloud = cfg.get_cloud_configuration()
                if cloud:
                    is_supervised = cloud.get("IsSupervised", False)
                    org = cloud.get("OrganizationName", "")
                    if is_supervised or org:
                        return True, org
                return False, ""
    except Exception as e:
        logger.error("MDM check failed: %s", e)
        return False, ""


async def run_verification(udid: Optional[str] = None, imei: str = "") -> VerificationResult:
    """Run all verification checks — SICKW API + local checks."""
    result = VerificationResult()

    # Local activation state
    result.activation_state = check_activation_local(udid)

    # Local MDM check
    result.mdm_enrolled, result.mdm_organization = check_mdm_local(udid)

    # SICKW API check (if valid IMEI available and API key configured)
    if imei and settings.sickw_api_key:
        from app.services.serial_decoder import validate_imei
        imei_check = validate_imei(imei)
        if not imei_check.is_valid:
            logger.warning("Skipping SICKW check — invalid IMEI: %s", imei)
            return result
        sickw_raw = await check_imei_sickw(imei)
        if "error" not in sickw_raw:
            parsed = _parse_sickw_result(sickw_raw)
            result.blacklist_status = parsed.blacklist_status
            result.fmi_status = parsed.fmi_status
            result.carrier = parsed.carrier
            result.carrier_locked = parsed.carrier_locked
            result.sim_lock_status = parsed.sim_lock_status
            result.raw = sickw_raw
        else:
            logger.warning("SICKW check failed: %s", sickw_raw.get("error"))

    return result
