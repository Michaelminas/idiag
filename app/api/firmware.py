"""Firmware management API routes — IPSW, signing, SHSH, restore, wipe."""

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.inventory import get_db
from app.models.firmware import (
    FirmwareVersion,
    IPSWCacheEntry,
    RestoreProgress,
    WipeRecord,
)
from app.services import firmware_manager, wipe_service

router = APIRouter(prefix="/api/firmware", tags=["firmware"])


# -- Request models --

class DownloadRequest(BaseModel):
    model: str
    version: str
    build_id: str = ""
    url: str = ""
    sha1: str = ""
    size_bytes: int = 0


class RestoreRequest(BaseModel):
    model: str
    version: Optional[str] = None


class WipeRequest(BaseModel):
    serial: str = ""
    imei: str = ""
    model: str = ""
    ios_version: str = ""
    operator: str = ""


# -- Signing / Firmware Info --

@router.get("/signed/{model}")
async def get_signed_versions(model: str) -> list[FirmwareVersion]:
    """Get currently signed iOS firmware versions for a device model."""
    return await asyncio.to_thread(firmware_manager.get_signed_versions, model)


# -- IPSW Cache --

@router.get("/cache")
async def list_cache() -> list[IPSWCacheEntry]:
    """List all cached IPSW files."""
    return await asyncio.to_thread(firmware_manager.list_cached_ipsw)


@router.delete("/cache/{model}/{version}")
async def evict_cached_ipsw(model: str, version: str):
    """Remove a specific IPSW from the cache."""
    path = await asyncio.to_thread(firmware_manager.get_cached_ipsw, model, version)
    if path and path.exists():
        path.unlink()
        return {"status": "deleted", "model": model, "version": version}
    raise HTTPException(status_code=404, detail="IPSW not found in cache")


@router.post("/download")
async def download_ipsw(req: DownloadRequest):
    """Trigger an IPSW download with real-time WebSocket progress."""
    from app.api.websocket import broadcast

    firmware = FirmwareVersion(
        version=req.version, build_id=req.build_id, model=req.model,
        url=req.url, sha1=req.sha1, size_bytes=req.size_bytes,
    )

    # If no URL provided, look it up from signed versions
    if not firmware.url:
        versions = await asyncio.to_thread(
            firmware_manager.get_signed_versions, req.model, False
        )
        match = next((v for v in versions if v.version == req.version), None)
        if not match:
            raise HTTPException(404, f"Version {req.version} not found for {req.model}")
        firmware = match

    loop = asyncio.get_event_loop()

    def _progress(p: RestoreProgress):
        asyncio.run_coroutine_threadsafe(
            broadcast("download_progress", p.model_dump()), loop
        )

    path = await asyncio.to_thread(firmware_manager.download_ipsw, firmware, progress_callback=_progress)
    if path:
        return {"status": "downloaded", "path": str(path)}
    raise HTTPException(500, "Download failed")


# -- SHSH Blobs --

@router.post("/shsh")
async def save_shsh_blobs(ecid: str, model: str, version: str):
    """Save SHSH blobs for a device + iOS version."""
    path = await asyncio.to_thread(
        firmware_manager.save_shsh_blobs, ecid, model, version
    )
    if path:
        await asyncio.to_thread(get_db().save_shsh_blob, ecid, model, version, str(path))
        return {"status": "saved", "path": str(path)}
    raise HTTPException(500, "Failed to save SHSH blobs")


@router.get("/shsh")
async def list_shsh_blobs(ecid: Optional[str] = None):
    """List saved SHSH blobs."""
    return await asyncio.to_thread(get_db().list_shsh_blobs, ecid)


# -- Device Mode Helpers --

@router.get("/mode/{udid}")
async def get_device_mode(udid: str):
    """Detect device mode: normal, recovery, dfu, or unknown."""
    mode = await asyncio.to_thread(firmware_manager.get_device_mode, udid)
    return {"udid": udid, "mode": mode}


@router.post("/dfu/{udid}")
async def enter_dfu_mode(udid: str):
    """Enter DFU mode (enters recovery first, user must complete button combo)."""
    ok = await asyncio.to_thread(firmware_manager.enter_dfu_mode, udid)
    if ok:
        return {"status": "recovery_entered", "message": "Now hold DFU button combo"}
    raise HTTPException(500, "Failed to enter recovery/DFU mode")


@router.post("/recovery/{udid}")
async def enter_recovery(udid: str):
    """Put device into recovery mode."""
    ok = await asyncio.to_thread(firmware_manager.enter_recovery_mode, udid)
    if ok:
        return {"status": "ok"}
    raise HTTPException(500, "Failed to enter recovery mode")


@router.delete("/recovery/{udid}")
async def exit_recovery(udid: str):
    """Kick device out of recovery mode."""
    ok = await asyncio.to_thread(firmware_manager.exit_recovery_mode, udid)
    if ok:
        return {"status": "ok"}
    raise HTTPException(500, "Failed to exit recovery mode")


# -- Restore --

@router.post("/restore/{udid}")
async def restore_device(udid: str, req: RestoreRequest):
    """Start a full firmware restore with real-time WebSocket progress."""
    from app.api.websocket import broadcast

    loop = asyncio.get_event_loop()

    def _progress(p: RestoreProgress):
        asyncio.run_coroutine_threadsafe(
            broadcast("restore_progress", p.model_dump()), loop
        )

    ok = await asyncio.to_thread(
        firmware_manager.restore_device, udid, req.model, req.version, _progress
    )

    if ok:
        return {"status": "restored", "version": req.version or "latest"}
    raise HTTPException(500, "Restore failed")


# -- Wipe --

@router.post("/wipe/{udid}")
async def wipe_device(udid: str, req: WipeRequest):
    """Erase device and generate erasure certificate with WebSocket progress."""
    from app.api.websocket import broadcast

    loop = asyncio.get_event_loop()
    asyncio.run_coroutine_threadsafe(
        broadcast("wipe_progress", {"udid": udid, "stage": "erasing", "percent": 0}), loop
    )

    ok = await asyncio.to_thread(wipe_service.erase_device, udid)

    record = WipeRecord(
        udid=udid,
        serial=req.serial,
        imei=req.imei,
        model=req.model,
        ios_version=req.ios_version,
        method="factory_reset",
        timestamp=datetime.now(),
        operator=req.operator,
        success=ok,
    )

    cert_path = await asyncio.to_thread(wipe_service.generate_certificate, record)

    if cert_path:
        record.cert_path = str(cert_path)

    device = await asyncio.to_thread(get_db().get_device_by_udid, udid)
    if device and device.id:
        record.device_id = device.id
        await asyncio.to_thread(
            get_db().save_wipe_record,
            device.id, udid, req.serial, req.imei, req.model,
            req.ios_version, "factory_reset", req.operator, ok,
            str(cert_path) if cert_path else "",
        )

    await broadcast("wipe_complete", {"udid": udid, "success": ok, "cert_path": str(cert_path or "")})

    return {
        "status": "erased" if ok else "failed",
        "cert_path": str(cert_path or ""),
    }


@router.get("/certificate/{device_id}")
async def download_certificate(device_id: int):
    """Download the most recent erasure certificate PDF for a device."""
    records = await asyncio.to_thread(get_db().list_wipe_records, device_id)
    if not records:
        raise HTTPException(404, "No wipe records found")

    latest = records[0]
    from pathlib import Path
    cert = Path(latest.cert_path)
    if not cert.exists():
        raise HTTPException(404, "Certificate file not found")

    return FileResponse(
        path=str(cert),
        media_type="application/pdf",
        filename=cert.name,
    )
