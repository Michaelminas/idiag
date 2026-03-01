"""Firmware management — IPSW download, cache, TSS signing, SHSH blobs, restore."""

import hashlib
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import httpx

from app.config import settings
from app.models.firmware import (
    FirmwareVersion,
    IPSWCacheEntry,
    RestoreProgress,
    SHSHBlob,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TSS / Signing Status (via ipsw.me free API)
# ---------------------------------------------------------------------------

def get_signed_versions(
    model_identifier: str, signed_only: bool = True
) -> list[FirmwareVersion]:
    """Query ipsw.me API for firmware versions of a device model.

    Args:
        model_identifier: Apple model ID, e.g. "iPhone14,2"
        signed_only: If True (default), only return currently signed versions.

    Returns:
        List of FirmwareVersion, empty list on error.
    """
    try:
        url = f"{settings.ipsw_api_base}/device/{model_identifier}?type=ipsw"
        resp = httpx.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        versions = []
        for fw in data.get("firmwares", []):
            fv = FirmwareVersion(
                version=fw.get("version", ""),
                build_id=fw.get("buildid", ""),
                model=fw.get("identifier", model_identifier),
                url=fw.get("url", ""),
                sha1=fw.get("sha1sum", ""),
                size_bytes=fw.get("filesize", 0),
                signed=fw.get("signed", False),
            )
            if signed_only and not fv.signed:
                continue
            versions.append(fv)
        return versions
    except Exception as e:
        logger.error("Failed to fetch signed versions for %s: %s", model_identifier, e)
        return []
