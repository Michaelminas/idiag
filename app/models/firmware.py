"""Firmware, restore, and wipe data models."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class FirmwareVersion(BaseModel):
    """A signed (or formerly signed) iOS firmware build."""
    version: str = ""
    build_id: str = ""
    model: str = ""  # e.g. "iPhone14,2"
    url: str = ""
    sha1: str = ""
    size_bytes: int = 0
    signed: bool = False


class IPSWCacheEntry(BaseModel):
    """An IPSW file stored in the local cache."""
    path: str = ""
    model: str = ""
    version: str = ""
    build_id: str = ""
    downloaded_at: Optional[datetime] = None
    size_bytes: int = 0


class SHSHBlob(BaseModel):
    """Saved SHSH2 blob for a specific device + iOS version."""
    id: Optional[int] = None
    ecid: str = ""
    device_model: str = ""
    ios_version: str = ""
    blob_path: str = ""
    saved_at: Optional[datetime] = None


RestoreStage = Literal[
    "downloading", "verifying", "preparing", "restoring", "complete", "error"
]


class RestoreProgress(BaseModel):
    """Progress update during firmware operations."""
    stage: RestoreStage = "preparing"
    percent: int = 0
    message: str = ""


WipeMethod = Literal["factory_reset", "dfu_restore"]


class WipeRecord(BaseModel):
    """Record of a device data erasure."""
    id: Optional[int] = None
    device_id: int = 0
    udid: str = ""
    serial: str = ""
    imei: str = ""
    model: str = ""
    ios_version: str = ""
    method: WipeMethod = "factory_reset"
    timestamp: Optional[datetime] = None
    operator: str = ""
    success: bool = False
    cert_path: str = ""
