"""FutureRestore service — downgrade/upgrade via futurerestore binary + SHSH blobs.

Wraps the futurerestore CLI tool to restore devices to unsigned iOS versions
using previously saved SHSH2 blobs. Follows the same subprocess-wrapper pattern
as bypass_tools.py.
"""

import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from app.models.tools import BypassResult, RestoreCompatibility

logger = logging.getLogger(__name__)

_TOOL_TIMEOUT = 1800  # 30 minutes — full restore can be slow


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def check_futurerestore_available() -> bool:
    """Check if the futurerestore binary is available on the system."""
    return shutil.which("futurerestore") is not None


# ---------------------------------------------------------------------------
# Compatibility Check
# ---------------------------------------------------------------------------


def check_compatibility(
    device_model: str,
    target_version: str,
    blob_path: Path,
) -> RestoreCompatibility:
    """Pre-flight check for SHSH blob restore viability.

    Validates that the blob file exists, is non-empty, and contains
    expected SHSH ticket markers. SEP compatibility is set optimistically
    (futurerestore checks at runtime).

    Args:
        device_model: Apple model identifier, e.g. "iPhone14,2".
        target_version: Target iOS version string, e.g. "16.0".
        blob_path: Path to the .shsh2 blob file.

    Returns:
        RestoreCompatibility with validation results.
    """
    # Check blob exists
    if not blob_path.exists():
        return RestoreCompatibility(
            compatible=False,
            target_version=target_version,
            blob_valid=False,
            sep_compatible=False,
            reason=f"Blob file not found: {blob_path}",
        )

    # Check blob is not empty
    try:
        content = blob_path.read_text(errors="replace")
    except Exception as e:
        return RestoreCompatibility(
            compatible=False,
            target_version=target_version,
            blob_valid=False,
            sep_compatible=False,
            reason=f"Failed to read blob file: {e}",
        )

    if not content.strip():
        return RestoreCompatibility(
            compatible=False,
            target_version=target_version,
            blob_valid=False,
            sep_compatible=False,
            reason="Blob file is empty",
        )

    # Check for SHSH ticket markers
    blob_valid = "ApImg4Ticket" in content or "generator" in content
    if not blob_valid:
        return RestoreCompatibility(
            compatible=False,
            target_version=target_version,
            blob_valid=False,
            sep_compatible=False,
            reason="Blob file does not contain valid SHSH ticket markers",
        )

    # Optimistic: SEP compatibility is checked at runtime by futurerestore
    return RestoreCompatibility(
        compatible=True,
        target_version=target_version,
        blob_valid=True,
        sep_compatible=True,
        reason=None,
    )


# ---------------------------------------------------------------------------
# Run FutureRestore
# ---------------------------------------------------------------------------


def run_futurerestore(
    udid: str,
    ipsw_path: Path,
    blob_path: Path,
    set_nonce: bool = True,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> BypassResult:
    """Run futurerestore to restore a device using an SHSH blob.

    Args:
        udid: Device UDID.
        ipsw_path: Path to the IPSW firmware file.
        blob_path: Path to the .shsh2 blob file.
        set_nonce: If True, include --set-nonce flag (default).
        progress_cb: Optional callback for progress messages.

    Returns:
        BypassResult with success/failure details (tool="futurerestore").
    """
    if not check_futurerestore_available():
        return BypassResult(
            success=False,
            tool="futurerestore",
            error="not_available",
            message="futurerestore is not installed or not on PATH",
            timestamp=datetime.now(),
        )

    if progress_cb:
        progress_cb(f"Starting futurerestore for device {udid}")

    cmd = [
        "futurerestore",
        "-t", str(blob_path),
        "--latest-sep",
        "--latest-baseband",
    ]
    if set_nonce:
        cmd.append("--set-nonce")
    cmd.append(str(ipsw_path))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_TOOL_TIMEOUT,
        )

        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            logger.warning(
                "futurerestore exited with code %d: %s", result.returncode, msg
            )
            if progress_cb:
                progress_cb(f"futurerestore failed: {msg}")
            return BypassResult(
                success=False,
                tool="futurerestore",
                error="process_error",
                message=msg,
                timestamp=datetime.now(),
            )

        if progress_cb:
            progress_cb("futurerestore completed successfully")

        return BypassResult(
            success=True,
            tool="futurerestore",
            message=result.stdout.strip() or "Restore complete",
            timestamp=datetime.now(),
        )

    except subprocess.TimeoutExpired:
        logger.error("futurerestore timed out after %d seconds", _TOOL_TIMEOUT)
        if progress_cb:
            progress_cb("futurerestore timed out")
        return BypassResult(
            success=False,
            tool="futurerestore",
            error="timeout",
            message=f"Process timed out after {_TOOL_TIMEOUT}s",
            timestamp=datetime.now(),
        )
    except Exception as e:
        logger.exception("Unexpected error running futurerestore: %s", e)
        if progress_cb:
            progress_cb(f"futurerestore error: {e}")
        return BypassResult(
            success=False,
            tool="futurerestore",
            error="process_error",
            message=str(e),
            timestamp=datetime.now(),
        )
