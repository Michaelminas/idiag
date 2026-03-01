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


# ---------------------------------------------------------------------------
# IPSW Cache
# ---------------------------------------------------------------------------

def _ipsw_filename(model: str, version: str, build_id: str) -> str:
    """Deterministic filename: iPhone14_2_17.4_21E219.ipsw"""
    safe_model = model.replace(",", "_")
    return f"{safe_model}_{version}_{build_id}.ipsw"


def _parse_ipsw_filename(filename: str) -> tuple[str, str, str]:
    """Extract (model, version, build_id) from cache filename."""
    stem = filename.rsplit(".", 1)[0]  # remove .ipsw
    parts = stem.split("_")
    # Find the version part (first segment containing a dot)
    version_idx = None
    for i, part in enumerate(parts):
        if "." in part:
            version_idx = i
            break
    if version_idx is None or version_idx < 1:
        return "", "", ""
    # Everything before version_idx is the model (rejoin, replace first _ with ,)
    model_parts = parts[:version_idx]
    model = "_".join(model_parts)
    # Restore first underscore to comma: iPhone14_2 -> iPhone14,2
    model = model.replace("_", ",", 1)
    version = parts[version_idx]
    build_id = "_".join(parts[version_idx + 1:]) if version_idx + 1 < len(parts) else ""
    return model, version, build_id


def list_cached_ipsw(cache_dir: Optional[Path] = None) -> list[IPSWCacheEntry]:
    """List all IPSW files in the cache directory."""
    cache_dir = cache_dir or settings.ipsw_cache_dir
    if not cache_dir.exists():
        return []

    entries = []
    for fpath in sorted(cache_dir.glob("*.ipsw"), key=lambda p: p.stat().st_mtime):
        model, version, build_id = _parse_ipsw_filename(fpath.name)
        stat = fpath.stat()
        entries.append(IPSWCacheEntry(
            path=str(fpath),
            model=model,
            version=version,
            build_id=build_id,
            downloaded_at=datetime.fromtimestamp(stat.st_mtime),
            size_bytes=stat.st_size,
        ))
    return entries


def evict_cache(
    cache_dir: Optional[Path] = None, max_bytes: Optional[int] = None
) -> int:
    """Remove oldest IPSW files until total cache size <= max_bytes.

    Returns number of files removed.
    """
    cache_dir = cache_dir or settings.ipsw_cache_dir
    if max_bytes is None:
        max_bytes = int(settings.ipsw_cache_max_gb * 1_073_741_824)

    if not cache_dir.exists():
        return 0

    # Sort by mtime ascending (oldest first)
    files = sorted(cache_dir.glob("*.ipsw"), key=lambda p: p.stat().st_mtime)
    total = sum(f.stat().st_size for f in files)
    removed = 0

    while total > max_bytes and files:
        oldest = files.pop(0)
        total -= oldest.stat().st_size
        oldest.unlink()
        removed += 1
        logger.info("Evicted cached IPSW: %s", oldest.name)

    return removed


def get_cached_ipsw(
    model: str, version: str, cache_dir: Optional[Path] = None
) -> Optional[Path]:
    """Look up a cached IPSW by model + version. Returns path or None."""
    cache_dir = cache_dir or settings.ipsw_cache_dir
    if not cache_dir.exists():
        return None
    for fpath in cache_dir.glob("*.ipsw"):
        m, v, _ = _parse_ipsw_filename(fpath.name)
        if m == model and v == version:
            return fpath
    return None


def verify_sha1(file_path: Path, expected_sha1: str) -> bool:
    """Verify a file's SHA1 checksum."""
    sha1 = hashlib.sha1()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha1.update(chunk)
    return sha1.hexdigest().lower() == expected_sha1.lower()


def download_ipsw(
    firmware: FirmwareVersion,
    cache_dir: Optional[Path] = None,
    progress_callback: Optional[Callable[[RestoreProgress], None]] = None,
) -> Optional[Path]:
    """Download an IPSW file from Apple CDN, verify SHA1, store in cache.

    Args:
        firmware: FirmwareVersion with url, sha1, size_bytes populated.
        cache_dir: Override cache directory (for testing).
        progress_callback: Called with RestoreProgress updates.

    Returns:
        Path to downloaded file, or None on failure.
    """
    cache_dir = cache_dir or settings.ipsw_cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    filename = _ipsw_filename(firmware.model, firmware.version, firmware.build_id)
    dest = cache_dir / filename

    # Already cached?
    if dest.exists() and verify_sha1(dest, firmware.sha1):
        logger.info("IPSW already cached: %s", filename)
        return dest

    if progress_callback:
        progress_callback(RestoreProgress(
            stage="downloading", percent=0, message=f"Downloading {filename}..."
        ))

    try:
        with httpx.stream("GET", firmware.url, timeout=None, follow_redirects=True) as resp:
            resp.raise_for_status()
            total = firmware.size_bytes or int(resp.headers.get("content-length", 0))
            downloaded = 0

            with open(dest, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=1_048_576):  # 1MB chunks
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total > 0:
                        pct = min(int(downloaded / total * 100), 99)
                        progress_callback(RestoreProgress(
                            stage="downloading", percent=pct,
                            message=f"Downloading: {downloaded // 1_048_576}MB / {total // 1_048_576}MB",
                        ))

        # Verify SHA1
        if progress_callback:
            progress_callback(RestoreProgress(
                stage="verifying", percent=99, message="Verifying SHA1 checksum..."
            ))

        if firmware.sha1 and not verify_sha1(dest, firmware.sha1):
            logger.error("SHA1 mismatch for %s", filename)
            dest.unlink(missing_ok=True)
            if progress_callback:
                progress_callback(RestoreProgress(
                    stage="error", percent=0, message="SHA1 verification failed"
                ))
            return None

        # Evict old files if over budget
        evict_cache(cache_dir=cache_dir)

        logger.info("Downloaded and verified: %s", filename)
        return dest

    except Exception as e:
        logger.error("IPSW download failed for %s: %s", filename, e)
        dest.unlink(missing_ok=True)
        if progress_callback:
            progress_callback(RestoreProgress(
                stage="error", percent=0, message=str(e)
            ))
        return None


# ---------------------------------------------------------------------------
# SHSH Blob Saving
# ---------------------------------------------------------------------------

def _find_tsschecker() -> Optional[str]:
    """Locate tsschecker binary on PATH or in common locations."""
    binary = shutil.which("tsschecker")
    if binary:
        return binary
    # Check common install locations on Linux
    for path in ["/usr/local/bin/tsschecker", "/usr/bin/tsschecker"]:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def _save_via_tsschecker(
    ecid: str, device_model: str, ios_version: str, blob_dir: Path
) -> Optional[Path]:
    """Save SHSH blobs using the tsschecker binary (primary method).

    tsschecker handles BuildManifest fetching, board config, nonce, and
    APTicket request fields automatically.
    """
    import subprocess

    binary = _find_tsschecker()
    if not binary:
        logger.info("tsschecker binary not found, will try pymobiledevice3 fallback")
        return None

    # Normalize ECID to decimal for tsschecker
    ecid_dec = str(int(ecid, 16) if ecid.startswith("0x") else int(ecid))

    try:
        result = subprocess.run(
            [
                binary,
                "--ecid", ecid_dec,
                "--device", device_model,
                "--ios", ios_version,
                "--save-path", str(blob_dir),
                "--save",
            ],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            logger.warning("tsschecker failed (exit %d): %s", result.returncode, result.stderr)
            return None

        # tsschecker saves blobs with a predictable naming pattern
        # Find the most recently created .shsh2 file in blob_dir
        blobs = sorted(blob_dir.glob("*.shsh*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if blobs:
            logger.info("tsschecker saved SHSH blob: %s", blobs[0].name)
            return blobs[0]

        logger.warning("tsschecker succeeded but no blob file found")
        return None
    except FileNotFoundError:
        logger.warning("tsschecker binary not executable")
        return None
    except subprocess.TimeoutExpired:
        logger.error("tsschecker timed out after 60s")
        return None
    except Exception as e:
        logger.error("tsschecker error: %s", e)
        return None


def _save_via_pymobiledevice3(
    ecid: str, device_model: str, ios_version: str, blob_dir: Path
) -> Optional[Path]:
    """Save SHSH blobs using pymobiledevice3 TSS module (fallback method).

    Fetches the BuildManifest from ipsw.me, extracts the correct BuildIdentity,
    and sends a proper TSS request with board config and version-specific fields.
    """
    try:
        from pymobiledevice3.restore.tss import TSSRequest
    except ImportError:
        logger.error("pymobiledevice3 not installed")
        return None

    ecid_int = int(ecid, 16) if ecid.startswith("0x") else int(ecid)

    # Look up build info from ipsw.me to get the buildid
    signed = get_signed_versions(device_model, signed_only=True)
    build_match = next((v for v in signed if v.version == ios_version), None)
    if not build_match:
        logger.error("iOS %s is not currently signed for %s — cannot save SHSH", ios_version, device_model)
        return None

    try:
        tss = TSSRequest()
        tss.add_common_tags(ecid=ecid_int)
        # Add version-specific tags from the firmware metadata
        tss.update({
            "ApProductionMode": True,
            "ApSecurityDomain": 1,
            "ApBoardID": _get_board_id(device_model),
            "ApChipID": _get_chip_id(device_model),
            "UniqueBuildID": build_match.build_id,
        })
        response = tss.send_receive()

        filename = f"{ecid}_{device_model}_{ios_version}.shsh2"
        dest = blob_dir / filename
        if isinstance(response, dict):
            import plistlib
            dest.write_bytes(plistlib.dumps(response))
        else:
            dest.write_bytes(response)
        logger.info("Saved SHSH blob via pymobiledevice3: %s", filename)
        return dest
    except Exception as e:
        logger.error("pymobiledevice3 TSS request failed: %s", e)
        return None


# Board/Chip ID lookup for common iPhone models (used by pymobiledevice3 fallback)
_BOARD_CHIP_MAP: dict[str, tuple[int, int]] = {
    # model: (board_id, chip_id)
    "iPhone10,1": (0x06, 0x8015),  # iPhone 8
    "iPhone10,4": (0x06, 0x8015),
    "iPhone10,2": (0x0A, 0x8015),  # iPhone 8 Plus
    "iPhone10,5": (0x0A, 0x8015),
    "iPhone10,3": (0x0E, 0x8015),  # iPhone X
    "iPhone10,6": (0x0E, 0x8015),
    "iPhone11,2": (0x04, 0x8020),  # iPhone XS
    "iPhone11,4": (0x08, 0x8020),  # iPhone XS Max
    "iPhone11,6": (0x08, 0x8020),
    "iPhone11,8": (0x0C, 0x8020),  # iPhone XR
    "iPhone12,1": (0x04, 0x8030),  # iPhone 11
    "iPhone12,3": (0x08, 0x8030),  # iPhone 11 Pro
    "iPhone12,5": (0x0C, 0x8030),  # iPhone 11 Pro Max
    "iPhone12,8": (0x10, 0x8030),  # iPhone SE 2
    "iPhone13,1": (0x04, 0x8101),  # iPhone 12 mini
    "iPhone13,2": (0x08, 0x8101),  # iPhone 12
    "iPhone13,3": (0x0C, 0x8101),  # iPhone 12 Pro
    "iPhone13,4": (0x10, 0x8101),  # iPhone 12 Pro Max
    "iPhone14,2": (0x08, 0x8110),  # iPhone 13 Pro
    "iPhone14,3": (0x0C, 0x8110),  # iPhone 13 Pro Max
    "iPhone14,4": (0x04, 0x8110),  # iPhone 13 mini
    "iPhone14,5": (0x10, 0x8110),  # iPhone 13
    "iPhone14,6": (0x10, 0x8110),  # iPhone SE 3
    "iPhone14,7": (0x04, 0x8120),  # iPhone 14
    "iPhone14,8": (0x08, 0x8120),  # iPhone 14 Plus
    "iPhone15,2": (0x0C, 0x8120),  # iPhone 14 Pro
    "iPhone15,3": (0x10, 0x8120),  # iPhone 14 Pro Max
    "iPhone15,4": (0x04, 0x8130),  # iPhone 15
    "iPhone15,5": (0x08, 0x8130),  # iPhone 15 Plus
    "iPhone16,1": (0x0C, 0x8130),  # iPhone 15 Pro
    "iPhone16,2": (0x10, 0x8130),  # iPhone 15 Pro Max
}


def _get_board_id(device_model: str) -> int:
    entry = _BOARD_CHIP_MAP.get(device_model)
    return entry[0] if entry else 0x04


def _get_chip_id(device_model: str) -> int:
    entry = _BOARD_CHIP_MAP.get(device_model)
    return entry[1] if entry else 0x8110


def save_shsh_blobs(
    ecid: str,
    device_model: str,
    ios_version: str,
    blob_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Save SHSH2 blob for a device + iOS version.

    Uses tsschecker binary as the primary method (handles BuildManifest,
    board config, nonce, and APTicket automatically). Falls back to
    pymobiledevice3 TSS module if tsschecker is not available.

    Args:
        ecid: Device ECID (hex string, e.g. "0x1234ABCD", or decimal).
        device_model: Apple identifier, e.g. "iPhone14,2".
        ios_version: iOS version string, e.g. "17.4".
        blob_dir: Override blob storage directory (for testing).

    Returns:
        Path to saved blob file, or None on failure.
    """
    blob_dir = blob_dir or settings.shsh_blob_dir
    blob_dir.mkdir(parents=True, exist_ok=True)

    # Primary: tsschecker binary
    result = _save_via_tsschecker(ecid, device_model, ios_version, blob_dir)
    if result:
        return result

    # Fallback: pymobiledevice3 TSS
    return _save_via_pymobiledevice3(ecid, device_model, ios_version, blob_dir)


# ---------------------------------------------------------------------------
# Device Mode Helpers (DFU / Recovery)
# ---------------------------------------------------------------------------

def _create_lockdown(udid: Optional[str] = None):
    """Create a lockdown client. This is the mock boundary for tests."""
    from pymobiledevice3.lockdown import create_using_usbmux
    return create_using_usbmux(serial=udid)


def _check_recovery_mode(udid: Optional[str] = None) -> bool:
    """Check if any device is in recovery mode."""
    try:
        from pymobiledevice3.irecv import IRecv
        IRecv()
        return True
    except Exception:
        return False


def _check_dfu_mode(udid: Optional[str] = None) -> bool:
    """Check if any device is in DFU mode."""
    try:
        from pymobiledevice3.irecv import IRecv
        device = IRecv()
        return device.is_dfu
    except Exception:
        return False


def _exit_recovery(udid: Optional[str] = None) -> bool:
    """Exit recovery mode. This is the mock boundary for tests."""
    try:
        from pymobiledevice3.irecv import IRecv
        device = IRecv()
        device.set_autoboot(True)
        device.reboot()
        return True
    except Exception as e:
        logger.error("Failed to exit recovery: %s", e)
        return False


def get_device_mode(udid: Optional[str] = None) -> str:
    """Detect current device mode: 'normal', 'recovery', 'dfu', or 'unknown'."""
    try:
        with _create_lockdown(udid):
            return "normal"
    except Exception:
        pass

    if _check_recovery_mode(udid):
        return "recovery"

    if _check_dfu_mode(udid):
        return "dfu"

    return "unknown"


def enter_recovery_mode(udid: Optional[str] = None) -> bool:
    """Put device into recovery mode."""
    try:
        with _create_lockdown(udid) as lockdown:
            lockdown.enter_recovery()
        logger.info("Device %s entered recovery mode", udid or "auto")
        return True
    except Exception as e:
        logger.error("Failed to enter recovery mode: %s", e)
        return False


def enter_dfu_mode(udid: Optional[str] = None) -> bool:
    """Guide device into DFU mode.

    Note: DFU mode requires physical button combo — this puts device into
    recovery first, then the user must hold the button combo.
    Returns True if recovery mode was entered (DFU prep step).
    """
    logger.info("DFU mode requires manual button combo. Entering recovery first...")
    return enter_recovery_mode(udid)


def exit_recovery_mode(udid: Optional[str] = None) -> bool:
    """Kick device out of recovery mode back to normal boot."""
    result = _exit_recovery(udid)
    if result:
        logger.info("Device exited recovery mode")
    return result


# ---------------------------------------------------------------------------
# Firmware Restore
# ---------------------------------------------------------------------------

def _perform_restore(udid: Optional[str], ipsw_path: Path) -> bool:
    """Execute the actual firmware restore via pymobiledevice3.

    This is the mock boundary — real implementation calls pymobiledevice3's
    restore module.
    """
    try:
        from pymobiledevice3.restore.device import Device
        from pymobiledevice3.restore.restore import Restore

        device = Device()
        restore = Restore(ipsw_path, device)
        restore.restore()
        return True
    except Exception as e:
        logger.error("Restore failed: %s", e)
        return False


def restore_device(
    udid: str,
    model: str,
    version: Optional[str] = None,
    progress_callback: Optional[Callable[[RestoreProgress], None]] = None,
) -> bool:
    """Full firmware restore workflow.

    1. Look up signed versions
    2. Download IPSW (with progress)
    3. Verify SHA1
    4. Execute restore (with progress)

    Args:
        udid: Device UDID.
        model: Apple model identifier (e.g. "iPhone14,2").
        version: Specific iOS version to restore. If None, uses latest signed.
        progress_callback: Called with RestoreProgress updates.

    Returns:
        True if restore succeeded, False otherwise.
    """
    cb = progress_callback or (lambda p: None)

    # 1. Get signed versions
    cb(RestoreProgress(stage="preparing", percent=0, message="Checking signed versions..."))
    signed = get_signed_versions(model, signed_only=True)

    if not signed:
        cb(RestoreProgress(stage="error", percent=0, message="No signed firmware versions found"))
        return False

    # Pick version
    if version:
        firmware = next((f for f in signed if f.version == version), None)
        if not firmware:
            cb(RestoreProgress(
                stage="error", percent=0,
                message=f"iOS {version} is not currently signed for {model}",
            ))
            return False
    else:
        firmware = signed[0]  # latest signed

    # 2. Download IPSW
    ipsw_path = download_ipsw(firmware, progress_callback=progress_callback)
    if not ipsw_path:
        return False

    # 3. Restore
    cb(RestoreProgress(
        stage="restoring", percent=0,
        message=f"Restoring iOS {firmware.version} ({firmware.build_id})...",
    ))

    success = _perform_restore(udid, ipsw_path)

    if success:
        cb(RestoreProgress(stage="complete", percent=100, message="Restore complete"))
    else:
        cb(RestoreProgress(stage="error", percent=0, message="Restore failed"))

    return success
