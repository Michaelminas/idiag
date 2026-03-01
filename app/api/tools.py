"""Tools API routes — bypass tools, futurerestore, cable check."""

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import bypass_tools, device_service, diagnostic_engine, futurerestore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


# -- Request models --


class ExtractRequest(BaseModel):
    data_types: list[str]
    target_dir: str


class FutureRestoreRequest(BaseModel):
    ipsw_path: str
    blob_path: str
    set_nonce: bool = True


# -- Availability --


@router.get("/availability")
async def check_availability():
    """Check which external tools are available on the system."""
    return {
        "checkra1n": bypass_tools.check_checkra1n_available(),
        "broque": bypass_tools.check_broque_available(),
        "ssh_ramdisk": bypass_tools.check_ssh_ramdisk_available(),
        "futurerestore": futurerestore.check_futurerestore_available(),
    }


# -- checkra1n --


@router.post("/checkra1n/{udid}")
async def run_checkra1n(udid: str):
    """Run checkra1n jailbreak on a device."""
    result = await asyncio.to_thread(bypass_tools.run_checkra1n, udid)
    return result.model_dump()


# -- Broque Ramdisk --


@router.post("/broque/{udid}")
async def run_broque_bypass(udid: str):
    """Run Broque Ramdisk bypass on a device."""
    result = await asyncio.to_thread(bypass_tools.run_broque_bypass, udid)
    return result.model_dump()


# -- SSH Ramdisk --


@router.post("/ssh-ramdisk/{udid}")
async def boot_ssh_ramdisk(udid: str):
    """Boot SSH Ramdisk on a device."""
    result = await asyncio.to_thread(bypass_tools.boot_ssh_ramdisk, udid)
    return result.model_dump()


@router.post("/ssh-ramdisk/{udid}/extract")
async def extract_data(udid: str, req: ExtractRequest):
    """Extract data from device via SSH Ramdisk."""
    result = await asyncio.to_thread(
        bypass_tools.extract_data, udid, req.target_dir, req.data_types
    )
    return result


# -- FutureRestore --


@router.get("/futurerestore/{udid}/check")
async def check_futurerestore_compatibility(
    udid: str, target_version: str, blob_path: str
):
    """Pre-flight check for SHSH blob restore viability."""
    result = futurerestore.check_compatibility(
        udid, target_version, Path(blob_path)
    )
    return result.model_dump()


@router.post("/futurerestore/{udid}")
async def run_futurerestore_restore(udid: str, req: FutureRestoreRequest):
    """Run futurerestore to restore a device using an SHSH blob."""
    result = await asyncio.to_thread(
        futurerestore.run_futurerestore,
        udid,
        Path(req.ipsw_path),
        Path(req.blob_path),
        req.set_nonce,
    )
    return result.model_dump()


# -- Cable Check --


@router.get("/cable/{udid}")
async def check_cable(udid: str):
    """Check USB cable quality for a connected device."""
    try:
        with device_service.get_lockdown_client(udid) as lockdown:
            result = diagnostic_engine.check_cable_quality(lockdown)
            return result.model_dump()
    except Exception as e:
        logger.error("Cable check failed for %s: %s", udid, e)
        raise HTTPException(status_code=500, detail=f"Cable check failed: {e}")
