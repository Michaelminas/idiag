"""Bypass tools — subprocess wrappers for checkra1n, Broque Ramdisk, SSH Ramdisk.

These are Linux-only binaries. On non-Linux or when the binary is not found,
functions return BypassResult(success=False, error="not_available").
"""

import logging
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from app.config import settings
from app.models.tools import BypassResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BROQUE_DIR: Path = settings.project_root / "tools" / "Broque-Ramdisk"
_TOOL_TIMEOUT = 600  # seconds

# Device paths for SSH ramdisk data extraction
_DEVICE_PATHS = {
    "photos": "/var/mobile/Media/DCIM",
    "contacts": "/var/mobile/Library/AddressBook",
    "messages": "/var/mobile/Library/SMS",
    "notes": "/var/mobile/Library/Notes",
    "voicemail": "/var/mobile/Library/Voicemail",
}


# ---------------------------------------------------------------------------
# checkra1n
# ---------------------------------------------------------------------------


def check_checkra1n_available() -> bool:
    """Check if the checkra1n binary is available on the system."""
    if sys.platform != "linux":
        return False
    return shutil.which("checkra1n") is not None


def run_checkra1n(
    udid: str,
    cli_mode: bool = True,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> BypassResult:
    """Run checkra1n jailbreak on a device.

    Args:
        udid: Device UDID.
        cli_mode: If True, run in CLI mode (-c flag).
        progress_cb: Optional callback for progress messages.

    Returns:
        BypassResult with success/failure details.
    """
    if not check_checkra1n_available():
        return BypassResult(
            success=False,
            tool="checkra1n",
            error="not_available",
            message="checkra1n is not installed or not on Linux",
            timestamp=datetime.now(),
        )

    if progress_cb:
        progress_cb(f"Starting checkra1n for device {udid}")

    cmd = ["checkra1n"]
    if cli_mode:
        cmd.append("-c")
    cmd.extend(["-u", udid])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_TOOL_TIMEOUT,
        )

        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            logger.warning("checkra1n exited with code %d: %s", result.returncode, msg)
            if progress_cb:
                progress_cb(f"checkra1n failed: {msg}")
            return BypassResult(
                success=False,
                tool="checkra1n",
                error="process_error",
                message=msg,
                timestamp=datetime.now(),
            )

        if progress_cb:
            progress_cb("checkra1n completed successfully")

        return BypassResult(
            success=True,
            tool="checkra1n",
            message=result.stdout.strip() or "Jailbreak complete",
            timestamp=datetime.now(),
        )

    except subprocess.TimeoutExpired:
        logger.error("checkra1n timed out after %d seconds", _TOOL_TIMEOUT)
        if progress_cb:
            progress_cb("checkra1n timed out")
        return BypassResult(
            success=False,
            tool="checkra1n",
            error="timeout",
            message=f"Process timed out after {_TOOL_TIMEOUT}s",
            timestamp=datetime.now(),
        )
    except Exception as e:
        logger.exception("Unexpected error running checkra1n: %s", e)
        if progress_cb:
            progress_cb(f"checkra1n error: {e}")
        return BypassResult(
            success=False,
            tool="checkra1n",
            error="process_error",
            message=str(e),
            timestamp=datetime.now(),
        )


# ---------------------------------------------------------------------------
# Broque Ramdisk
# ---------------------------------------------------------------------------


def check_broque_available() -> bool:
    """Check if Broque Ramdisk tools are available."""
    if sys.platform != "linux":
        return False
    if not _BROQUE_DIR.is_dir():
        return False
    bypass_sh = _BROQUE_DIR / "bypass.sh"
    return bypass_sh.exists()


def run_broque_bypass(
    udid: str,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> BypassResult:
    """Run Broque Ramdisk bypass on a device.

    Args:
        udid: Device UDID.
        progress_cb: Optional callback for progress messages.

    Returns:
        BypassResult with success/failure details.
    """
    if not check_broque_available():
        return BypassResult(
            success=False,
            tool="broque",
            error="not_available",
            message="Broque Ramdisk tools not found",
            timestamp=datetime.now(),
        )

    if progress_cb:
        progress_cb(f"Starting Broque Ramdisk bypass for device {udid}")

    bypass_sh = _BROQUE_DIR / "bypass.sh"
    cmd = ["bash", str(bypass_sh), udid]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_TOOL_TIMEOUT,
        )

        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            logger.warning("Broque bypass exited with code %d: %s", result.returncode, msg)
            if progress_cb:
                progress_cb(f"Broque bypass failed: {msg}")
            return BypassResult(
                success=False,
                tool="broque",
                error="process_error",
                message=msg,
                timestamp=datetime.now(),
            )

        if progress_cb:
            progress_cb("Broque Ramdisk bypass completed successfully")

        return BypassResult(
            success=True,
            tool="broque",
            message=result.stdout.strip() or "Bypass complete",
            timestamp=datetime.now(),
        )

    except subprocess.TimeoutExpired:
        logger.error("Broque bypass timed out after %d seconds", _TOOL_TIMEOUT)
        if progress_cb:
            progress_cb("Broque bypass timed out")
        return BypassResult(
            success=False,
            tool="broque",
            error="timeout",
            message=f"Process timed out after {_TOOL_TIMEOUT}s",
            timestamp=datetime.now(),
        )
    except Exception as e:
        logger.exception("Unexpected error running Broque bypass: %s", e)
        if progress_cb:
            progress_cb(f"Broque bypass error: {e}")
        return BypassResult(
            success=False,
            tool="broque",
            error="process_error",
            message=str(e),
            timestamp=datetime.now(),
        )


# ---------------------------------------------------------------------------
# SSH Ramdisk
# ---------------------------------------------------------------------------


def check_ssh_ramdisk_available() -> bool:
    """Check if the sshrd binary is available on the system."""
    if sys.platform != "linux":
        return False
    return shutil.which("sshrd") is not None


def boot_ssh_ramdisk(
    udid: str,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> BypassResult:
    """Boot SSH Ramdisk on a device.

    Args:
        udid: Device UDID.
        progress_cb: Optional callback for progress messages.

    Returns:
        BypassResult with success/failure details.
    """
    if not check_ssh_ramdisk_available():
        return BypassResult(
            success=False,
            tool="ssh_ramdisk",
            error="not_available",
            message="sshrd is not installed or not on Linux",
            timestamp=datetime.now(),
        )

    if progress_cb:
        progress_cb(f"Booting SSH Ramdisk for device {udid}")

    cmd = ["sshrd", "boot", udid]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_TOOL_TIMEOUT,
        )

        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            logger.warning("sshrd boot exited with code %d: %s", result.returncode, msg)
            if progress_cb:
                progress_cb(f"SSH Ramdisk boot failed: {msg}")
            return BypassResult(
                success=False,
                tool="ssh_ramdisk",
                error="process_error",
                message=msg,
                timestamp=datetime.now(),
            )

        if progress_cb:
            progress_cb("SSH Ramdisk booted successfully")

        return BypassResult(
            success=True,
            tool="ssh_ramdisk",
            message=result.stdout.strip() or "SSH Ramdisk booted",
            timestamp=datetime.now(),
        )

    except subprocess.TimeoutExpired:
        logger.error("sshrd boot timed out after %d seconds", _TOOL_TIMEOUT)
        if progress_cb:
            progress_cb("SSH Ramdisk boot timed out")
        return BypassResult(
            success=False,
            tool="ssh_ramdisk",
            error="timeout",
            message=f"Process timed out after {_TOOL_TIMEOUT}s",
            timestamp=datetime.now(),
        )
    except Exception as e:
        logger.exception("Unexpected error booting SSH Ramdisk: %s", e)
        if progress_cb:
            progress_cb(f"SSH Ramdisk error: {e}")
        return BypassResult(
            success=False,
            tool="ssh_ramdisk",
            error="process_error",
            message=str(e),
            timestamp=datetime.now(),
        )


def extract_data(
    udid: str,
    target_dir: str,
    data_types: list[str],
    progress_cb: Optional[Callable[[str], None]] = None,
) -> dict:
    """Extract data from device via SSH Ramdisk using scp.

    Args:
        udid: Device UDID.
        target_dir: Local directory to copy files into.
        data_types: List of data types to extract (photos, contacts, messages, etc.).
        progress_cb: Optional callback for progress messages.

    Returns:
        Dict of {dtype: {success: bool, message: str, count: int}}.
    """
    results: dict = {}

    if not check_ssh_ramdisk_available():
        for dtype in data_types:
            results[dtype] = {
                "success": False,
                "message": "sshrd is not installed or not on Linux",
                "count": 0,
            }
        return results

    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    for dtype in data_types:
        device_path = _DEVICE_PATHS.get(dtype)
        if not device_path:
            results[dtype] = {
                "success": False,
                "message": f"Unknown data type: {dtype}",
                "count": 0,
            }
            continue

        if progress_cb:
            progress_cb(f"Extracting {dtype} from device {udid}")

        dest = target / dtype
        dest.mkdir(parents=True, exist_ok=True)

        cmd = ["scp", "-r", f"root@localhost:{device_path}/*", str(dest)]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_TOOL_TIMEOUT,
            )

            if result.returncode != 0:
                msg = result.stderr.strip() or "Copy failed"
                logger.warning("scp for %s failed: %s", dtype, msg)
                results[dtype] = {
                    "success": False,
                    "message": msg,
                    "count": 0,
                }
            else:
                stdout = result.stdout.strip()
                results[dtype] = {
                    "success": True,
                    "message": stdout or f"{dtype} extracted successfully",
                    "count": len(list(dest.iterdir())) if dest.exists() else 0,
                }

            if progress_cb:
                progress_cb(f"Finished extracting {dtype}")

        except subprocess.TimeoutExpired:
            logger.error("scp for %s timed out", dtype)
            results[dtype] = {
                "success": False,
                "message": f"Timed out after {_TOOL_TIMEOUT}s",
                "count": 0,
            }
        except Exception as e:
            logger.exception("Error extracting %s: %s", dtype, e)
            results[dtype] = {
                "success": False,
                "message": str(e),
                "count": 0,
            }

    return results
