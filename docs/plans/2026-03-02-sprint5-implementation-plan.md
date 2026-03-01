# Sprint 5: Edge Cases & Hardening — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add bypass/recovery tools (checkra1n, Broque Ramdisk, SSH Ramdisk, FutureRestore), real-time syslog viewer, USB cable check, error handling hardening, and bootable USB build script.

**Architecture:** Subprocess wrappers for external Linux binaries with stub mode on non-Linux. Syslog streaming via pymobiledevice3 OsTraceService over WebSocket. Error hardening via decorators and global exception handler. All new services follow existing stateless-function pattern from firmware_manager.py.

**Tech Stack:** Python 3.11, FastAPI, pymobiledevice3, subprocess, asyncio, WebSocket, live-build (USB)

**Test command:** `PYTHONPATH="D:/pip-packages;D:/Project - idiag" python -c "import sys; sys.path.insert(0,'D:/pip-packages'); import pytest; sys.exit(pytest.main(['-v', 'tests/']))"`

---

## Task 1: Models — `app/models/tools.py`

**Files:**
- Create: `app/models/tools.py`
- Test: `tests/test_tools_models.py`

**Step 1: Write model validation tests**

Create `tests/test_tools_models.py`:

```python
"""Tests for Sprint 5 tool models."""
from datetime import datetime

from app.models.tools import (
    BypassResult,
    CableCheckResult,
    RestoreCompatibility,
    SyslogEntry,
    SyslogFilter,
)


class TestBypassResult:
    def test_defaults(self):
        r = BypassResult(success=False, tool="checkra1n")
        assert r.success is False
        assert r.tool == "checkra1n"
        assert r.error is None
        assert r.message is None
        assert r.timestamp is None

    def test_full(self):
        r = BypassResult(
            success=True,
            tool="broque",
            error=None,
            message="Bypass complete",
            timestamp=datetime(2026, 3, 2),
        )
        assert r.tool == "broque"
        assert r.message == "Bypass complete"

    def test_tool_literal(self):
        for t in ("checkra1n", "broque", "ssh_ramdisk"):
            r = BypassResult(success=False, tool=t)
            assert r.tool == t


class TestRestoreCompatibility:
    def test_compatible(self):
        rc = RestoreCompatibility(
            compatible=True,
            target_version="15.4.1",
            blob_valid=True,
            sep_compatible=True,
        )
        assert rc.compatible is True
        assert rc.reason is None

    def test_incompatible(self):
        rc = RestoreCompatibility(
            compatible=False,
            target_version="16.0",
            blob_valid=True,
            sep_compatible=False,
            reason="Current SEP incompatible with target iOS",
        )
        assert rc.compatible is False
        assert "SEP" in rc.reason


class TestSyslogEntry:
    def test_entry(self):
        e = SyslogEntry(
            timestamp=datetime(2026, 3, 2, 10, 0, 0),
            process="SpringBoard",
            pid=42,
            level="Error",
            message="Something failed",
        )
        assert e.process == "SpringBoard"
        assert e.level == "Error"


class TestSyslogFilter:
    def test_defaults(self):
        f = SyslogFilter()
        assert f.process is None
        assert f.level is None
        assert f.keyword is None

    def test_with_values(self):
        f = SyslogFilter(process="kernel", level="Warning", keyword="panic")
        assert f.process == "kernel"


class TestCableCheckResult:
    def test_defaults(self):
        c = CableCheckResult(
            connection_type="USB 2.0",
            charge_capable=True,
            data_capable=True,
        )
        assert c.warnings == []
        assert c.negotiated_speed is None

    def test_with_warnings(self):
        c = CableCheckResult(
            connection_type="Unknown",
            charge_capable=False,
            data_capable=False,
            warnings=["No MFi chip detected", "Low data throughput"],
        )
        assert len(c.warnings) == 2
```

**Step 2: Run tests — expect FAIL (models don't exist)**

```bash
pytest tests/test_tools_models.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.models.tools'`

**Step 3: Create `app/models/tools.py`**

```python
"""Pydantic models for Sprint 5 tools — bypass, syslog, cable check."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class BypassResult(BaseModel):
    """Result from a bypass tool operation (checkra1n, Broque, SSH Ramdisk)."""

    success: bool
    tool: Literal["checkra1n", "broque", "ssh_ramdisk"]
    error: Optional[str] = None
    message: Optional[str] = None
    timestamp: Optional[datetime] = None


class RestoreCompatibility(BaseModel):
    """FutureRestore compatibility check result."""

    compatible: bool
    target_version: str
    blob_valid: bool
    sep_compatible: bool
    reason: Optional[str] = None


class SyslogEntry(BaseModel):
    """A single parsed syslog line from an iOS device."""

    timestamp: datetime
    process: str
    pid: int
    level: Literal[
        "Emergency", "Alert", "Critical", "Error",
        "Warning", "Notice", "Info", "Debug",
    ]
    message: str


class SyslogFilter(BaseModel):
    """Client-side filter for syslog streaming."""

    process: Optional[str] = None
    level: Optional[str] = None
    keyword: Optional[str] = None


class CableCheckResult(BaseModel):
    """USB cable quality assessment."""

    connection_type: str  # "USB 2.0", "USB 3.0", "Unknown"
    charge_capable: bool
    data_capable: bool
    negotiated_speed: Optional[str] = None
    warnings: list[str] = []
```

**Step 4: Run tests — expect PASS**

```bash
pytest tests/test_tools_models.py -v
```

**Step 5: Commit**

```bash
git add app/models/tools.py tests/test_tools_models.py
git commit -m "feat(sprint5): add Pydantic models for bypass tools, syslog, cable check"
```

---

## Task 2: Bypass Tools Service — `app/services/bypass_tools.py`

**Files:**
- Create: `app/services/bypass_tools.py`
- Test: `tests/test_bypass_tools.py`

**Step 1: Write tests**

Create `tests/test_bypass_tools.py`:

```python
"""Tests for bypass tools service — checkra1n, Broque Ramdisk, SSH Ramdisk."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.bypass_tools import (
    boot_ssh_ramdisk,
    check_broque_available,
    check_checkra1n_available,
    check_ssh_ramdisk_available,
    extract_data,
    run_broque_bypass,
    run_checkra1n,
)


class TestCheckra1nAvailability:
    @patch("shutil.which", return_value="/usr/bin/checkra1n")
    def test_available(self, mock_which):
        assert check_checkra1n_available() is True

    @patch("shutil.which", return_value=None)
    def test_not_available(self, mock_which):
        assert check_checkra1n_available() is False


class TestRunCheckra1n:
    @patch("shutil.which", return_value=None)
    def test_not_available_returns_failure(self, mock_which):
        result = run_checkra1n("abc123")
        assert result.success is False
        assert result.error == "not_available"
        assert result.tool == "checkra1n"

    @patch("shutil.which", return_value="/usr/bin/checkra1n")
    @patch("subprocess.run")
    def test_success(self, mock_run, mock_which):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="All done", stderr=""
        )
        result = run_checkra1n("abc123")
        assert result.success is True
        assert result.tool == "checkra1n"
        mock_run.assert_called_once()
        # Verify the command includes the UDID
        cmd = mock_run.call_args[0][0]
        assert "checkra1n" in cmd[0]

    @patch("shutil.which", return_value="/usr/bin/checkra1n")
    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="", timeout=600))
    def test_timeout(self, mock_run, mock_which):
        result = run_checkra1n("abc123")
        assert result.success is False
        assert result.error == "timeout"

    @patch("shutil.which", return_value="/usr/bin/checkra1n")
    @patch("subprocess.run")
    def test_nonzero_exit(self, mock_run, mock_which):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Device not in DFU mode"
        )
        result = run_checkra1n("abc123")
        assert result.success is False
        assert result.error == "process_error"

    @patch("shutil.which", return_value="/usr/bin/checkra1n")
    @patch("subprocess.run")
    def test_progress_callback(self, mock_run, mock_which):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Done", stderr=""
        )
        cb = MagicMock()
        run_checkra1n("abc123", progress_cb=cb)
        assert cb.call_count >= 1


class TestBroqueAvailability:
    @patch("app.services.bypass_tools._BROQUE_DIR")
    def test_available(self, mock_dir):
        mock_dir.__truediv__ = MagicMock(return_value=MagicMock(exists=MagicMock(return_value=True)))
        mock_dir.exists = MagicMock(return_value=True)
        # Will check dir exists + script exists
        with patch("pathlib.Path.exists", return_value=True):
            assert check_broque_available() is True

    @patch("pathlib.Path.exists", return_value=False)
    def test_not_available(self, mock_exists):
        assert check_broque_available() is False


class TestRunBroque:
    @patch("pathlib.Path.exists", return_value=False)
    def test_not_available_returns_failure(self, mock_exists):
        result = run_broque_bypass("abc123")
        assert result.success is False
        assert result.error == "not_available"
        assert result.tool == "broque"

    @patch("app.services.bypass_tools.check_broque_available", return_value=True)
    @patch("subprocess.run")
    def test_success(self, mock_run, mock_avail):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Bypass complete", stderr=""
        )
        result = run_broque_bypass("abc123")
        assert result.success is True
        assert result.tool == "broque"


class TestSSHRamdisk:
    @patch("shutil.which", return_value=None)
    def test_not_available(self, mock_which):
        assert check_ssh_ramdisk_available() is False

    @patch("shutil.which", return_value=None)
    def test_boot_not_available(self, mock_which):
        result = boot_ssh_ramdisk("abc123")
        assert result.success is False
        assert result.error == "not_available"

    @patch("app.services.bypass_tools.check_ssh_ramdisk_available", return_value=True)
    @patch("subprocess.run")
    def test_boot_success(self, mock_run, mock_avail):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Ramdisk booted", stderr=""
        )
        result = boot_ssh_ramdisk("abc123")
        assert result.success is True
        assert result.tool == "ssh_ramdisk"


class TestExtractData:
    @patch("subprocess.run")
    def test_extract_photos(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Copied 42 files", stderr=""
        )
        result = extract_data("abc123", Path("/tmp/out"), ["photos"])
        assert "photos" in result
        assert result["photos"]["success"] is True

    @patch("subprocess.run", side_effect=FileNotFoundError("scp not found"))
    def test_extract_tool_missing(self, mock_run):
        result = extract_data("abc123", Path("/tmp/out"), ["photos"])
        assert result["photos"]["success"] is False
```

**Step 2: Run tests — expect FAIL**

```bash
pytest tests/test_bypass_tools.py -v
```

**Step 3: Create `app/services/bypass_tools.py`**

```python
"""Subprocess wrappers for bypass/recovery tools (checkra1n, Broque Ramdisk, SSH Ramdisk).

These tools are Linux-only binaries. On non-Linux or when the binary is not found,
functions return BypassResult(success=False, error="not_available") instead of crashing.
"""

import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from app.config import settings
from app.models.tools import BypassResult

logger = logging.getLogger(__name__)

# Default locations for external tools
_BROQUE_DIR = settings.project_root / "tools" / "Broque-Ramdisk"
_SSH_RAMDISK_SCRIPT = "sshrd"  # Expected in PATH

_TOOL_TIMEOUT = 600  # 10 minutes max per operation


# ---------------------------------------------------------------------------
# checkra1n — Jailbreak for A5-A11 devices (iOS 12.0-14.8.1)
# ---------------------------------------------------------------------------

def check_checkra1n_available() -> bool:
    """Check if checkra1n binary is available in PATH."""
    return shutil.which("checkra1n") is not None


def run_checkra1n(
    udid: str,
    cli_mode: bool = True,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> BypassResult:
    """Run checkra1n jailbreak on a device.

    Device must be in DFU mode. Use firmware_manager.enter_dfu_mode() first.
    """
    if not check_checkra1n_available():
        return BypassResult(
            success=False,
            tool="checkra1n",
            error="not_available",
            message="checkra1n binary not found in PATH",
            timestamp=datetime.now(),
        )

    cmd = ["checkra1n", "-c", "-u", udid] if cli_mode else ["checkra1n", "-u", udid]
    if progress_cb:
        progress_cb("Starting checkra1n...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_TOOL_TIMEOUT,
        )
        if progress_cb:
            progress_cb("checkra1n finished")

        if result.returncode == 0:
            return BypassResult(
                success=True,
                tool="checkra1n",
                message=result.stdout.strip() or "Jailbreak applied successfully",
                timestamp=datetime.now(),
            )
        return BypassResult(
            success=False,
            tool="checkra1n",
            error="process_error",
            message=result.stderr.strip() or f"Exit code {result.returncode}",
            timestamp=datetime.now(),
        )
    except subprocess.TimeoutExpired:
        logger.error("checkra1n timed out after %ds for %s", _TOOL_TIMEOUT, udid)
        return BypassResult(
            success=False,
            tool="checkra1n",
            error="timeout",
            message=f"Timed out after {_TOOL_TIMEOUT}s",
            timestamp=datetime.now(),
        )
    except Exception as e:
        logger.error("checkra1n failed for %s: %s", udid, e)
        return BypassResult(
            success=False,
            tool="checkra1n",
            error="exception",
            message=str(e),
            timestamp=datetime.now(),
        )


# ---------------------------------------------------------------------------
# Broque Ramdisk — iCloud bypass for A9-A11 devices
# ---------------------------------------------------------------------------

def check_broque_available() -> bool:
    """Check if Broque Ramdisk repo is cloned and main script exists."""
    script = _BROQUE_DIR / "bypass.sh"
    return _BROQUE_DIR.exists() and script.exists()


def run_broque_bypass(
    udid: str,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> BypassResult:
    """Run Broque Ramdisk iCloud bypass. Device must be in DFU mode."""
    if not check_broque_available():
        return BypassResult(
            success=False,
            tool="broque",
            error="not_available",
            message="Broque Ramdisk not found at " + str(_BROQUE_DIR),
            timestamp=datetime.now(),
        )

    if progress_cb:
        progress_cb("Starting Broque Ramdisk bypass...")

    try:
        result = subprocess.run(
            ["bash", str(_BROQUE_DIR / "bypass.sh"), udid],
            capture_output=True,
            text=True,
            timeout=_TOOL_TIMEOUT,
            cwd=str(_BROQUE_DIR),
        )
        if progress_cb:
            progress_cb("Broque bypass finished")

        if result.returncode == 0:
            return BypassResult(
                success=True,
                tool="broque",
                message=result.stdout.strip() or "iCloud bypass applied",
                timestamp=datetime.now(),
            )
        return BypassResult(
            success=False,
            tool="broque",
            error="process_error",
            message=result.stderr.strip() or f"Exit code {result.returncode}",
            timestamp=datetime.now(),
        )
    except subprocess.TimeoutExpired:
        logger.error("Broque bypass timed out for %s", udid)
        return BypassResult(
            success=False,
            tool="broque",
            error="timeout",
            message=f"Timed out after {_TOOL_TIMEOUT}s",
            timestamp=datetime.now(),
        )
    except Exception as e:
        logger.error("Broque bypass failed for %s: %s", udid, e)
        return BypassResult(
            success=False,
            tool="broque",
            error="exception",
            message=str(e),
            timestamp=datetime.now(),
        )


# ---------------------------------------------------------------------------
# SSH Ramdisk — Data extraction from passcode-locked devices (A9-A11)
# ---------------------------------------------------------------------------

def check_ssh_ramdisk_available() -> bool:
    """Check if SSH ramdisk tool (sshrd) is available in PATH."""
    return shutil.which(_SSH_RAMDISK_SCRIPT) is not None


def boot_ssh_ramdisk(
    udid: str,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> BypassResult:
    """Boot an SSH ramdisk on the device for data extraction."""
    if not check_ssh_ramdisk_available():
        return BypassResult(
            success=False,
            tool="ssh_ramdisk",
            error="not_available",
            message="sshrd tool not found in PATH",
            timestamp=datetime.now(),
        )

    if progress_cb:
        progress_cb("Booting SSH ramdisk...")

    try:
        result = subprocess.run(
            [_SSH_RAMDISK_SCRIPT, "boot", udid],
            capture_output=True,
            text=True,
            timeout=_TOOL_TIMEOUT,
        )
        if progress_cb:
            progress_cb("SSH ramdisk boot complete")

        if result.returncode == 0:
            return BypassResult(
                success=True,
                tool="ssh_ramdisk",
                message=result.stdout.strip() or "SSH ramdisk booted",
                timestamp=datetime.now(),
            )
        return BypassResult(
            success=False,
            tool="ssh_ramdisk",
            error="process_error",
            message=result.stderr.strip() or f"Exit code {result.returncode}",
            timestamp=datetime.now(),
        )
    except subprocess.TimeoutExpired:
        logger.error("SSH ramdisk boot timed out for %s", udid)
        return BypassResult(
            success=False,
            tool="ssh_ramdisk",
            error="timeout",
            message=f"Timed out after {_TOOL_TIMEOUT}s",
            timestamp=datetime.now(),
        )
    except Exception as e:
        logger.error("SSH ramdisk boot failed for %s: %s", udid, e)
        return BypassResult(
            success=False,
            tool="ssh_ramdisk",
            error="exception",
            message=str(e),
            timestamp=datetime.now(),
        )


def extract_data(
    udid: str,
    target_dir: Path,
    data_types: list[str],
) -> dict:
    """Extract data from a device via SSH ramdisk.

    Args:
        udid: Device UDID.
        target_dir: Local directory to save extracted files.
        data_types: List of data types to extract (e.g. ["photos", "contacts"]).

    Returns:
        Dict mapping each data_type to {"success": bool, "message": str, "count": int}.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    # Map data types to device paths
    type_paths = {
        "photos": "/mnt1/Media/DCIM",
        "contacts": "/mnt1/Mobile/Library/AddressBook",
        "messages": "/mnt1/Mobile/Library/SMS",
        "notes": "/mnt1/Mobile/Library/Notes",
    }

    for dtype in data_types:
        remote_path = type_paths.get(dtype)
        if not remote_path:
            results[dtype] = {"success": False, "message": f"Unknown data type: {dtype}", "count": 0}
            continue

        dest = target_dir / dtype
        dest.mkdir(parents=True, exist_ok=True)

        try:
            result = subprocess.run(
                ["scp", "-r", f"root@localhost:{remote_path}/*", str(dest)],
                capture_output=True,
                text=True,
                timeout=_TOOL_TIMEOUT,
            )
            if result.returncode == 0:
                count = len(list(dest.rglob("*")))
                results[dtype] = {"success": True, "message": f"Copied {count} files", "count": count}
            else:
                results[dtype] = {"success": False, "message": result.stderr.strip(), "count": 0}
        except Exception as e:
            logger.error("Data extraction (%s) failed for %s: %s", dtype, udid, e)
            results[dtype] = {"success": False, "message": str(e), "count": 0}

    return results
```

**Step 4: Run tests — expect PASS**

```bash
pytest tests/test_bypass_tools.py -v
```

**Step 5: Commit**

```bash
git add app/services/bypass_tools.py tests/test_bypass_tools.py
git commit -m "feat(sprint5): add bypass tools service — checkra1n, Broque, SSH Ramdisk"
```

---

## Task 3: FutureRestore Service — `app/services/futurerestore.py`

**Files:**
- Create: `app/services/futurerestore.py`
- Test: `tests/test_futurerestore.py`

**Step 1: Write tests**

Create `tests/test_futurerestore.py`:

```python
"""Tests for FutureRestore downgrade service."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.futurerestore import (
    check_compatibility,
    check_futurerestore_available,
    run_futurerestore,
)


class TestFutureRestoreAvailability:
    @patch("shutil.which", return_value="/usr/bin/futurerestore")
    def test_available(self, mock_which):
        assert check_futurerestore_available() is True

    @patch("shutil.which", return_value=None)
    def test_not_available(self, mock_which):
        assert check_futurerestore_available() is False


class TestCheckCompatibility:
    def test_blob_not_found(self, tmp_path):
        result = check_compatibility(
            device_model="iPhone10,6",
            target_version="15.4.1",
            blob_path=tmp_path / "nonexistent.shsh2",
        )
        assert result.compatible is False
        assert result.blob_valid is False

    def test_valid_blob(self, tmp_path):
        blob = tmp_path / "blob.shsh2"
        blob.write_text('{"ApImg4Ticket": "base64data"}')
        result = check_compatibility(
            device_model="iPhone10,6",
            target_version="15.4.1",
            blob_path=blob,
        )
        assert result.blob_valid is True
        assert result.target_version == "15.4.1"

    def test_empty_blob(self, tmp_path):
        blob = tmp_path / "blob.shsh2"
        blob.write_text("")
        result = check_compatibility(
            device_model="iPhone10,6",
            target_version="15.4.1",
            blob_path=blob,
        )
        assert result.blob_valid is False


class TestRunFutureRestore:
    @patch("shutil.which", return_value=None)
    def test_not_available(self, mock_which, tmp_path):
        result = run_futurerestore(
            udid="abc123",
            ipsw_path=tmp_path / "fw.ipsw",
            blob_path=tmp_path / "blob.shsh2",
        )
        assert result.success is False
        assert result.error == "not_available"
        assert result.tool == "checkra1n"  # reuses BypassResult

    @patch("shutil.which", return_value="/usr/bin/futurerestore")
    @patch("subprocess.run")
    def test_success(self, mock_run, mock_which, tmp_path):
        ipsw = tmp_path / "fw.ipsw"
        ipsw.touch()
        blob = tmp_path / "blob.shsh2"
        blob.write_text("blob_data")

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Restore successful", stderr=""
        )
        result = run_futurerestore("abc123", ipsw, blob)
        assert result.success is True
        cmd = mock_run.call_args[0][0]
        assert "futurerestore" in cmd[0]
        assert str(blob) in cmd
        assert str(ipsw) in cmd

    @patch("shutil.which", return_value="/usr/bin/futurerestore")
    @patch("subprocess.run")
    def test_failure(self, mock_run, mock_which, tmp_path):
        ipsw = tmp_path / "fw.ipsw"
        ipsw.touch()
        blob = tmp_path / "blob.shsh2"
        blob.write_text("blob_data")

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="SEP not compatible"
        )
        result = run_futurerestore("abc123", ipsw, blob)
        assert result.success is False
        assert result.error == "process_error"

    @patch("shutil.which", return_value="/usr/bin/futurerestore")
    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="", timeout=600))
    def test_timeout(self, mock_run, mock_which, tmp_path):
        ipsw = tmp_path / "fw.ipsw"
        ipsw.touch()
        blob = tmp_path / "blob.shsh2"
        blob.write_text("blob_data")

        result = run_futurerestore("abc123", ipsw, blob)
        assert result.success is False
        assert result.error == "timeout"

    @patch("shutil.which", return_value="/usr/bin/futurerestore")
    @patch("subprocess.run")
    def test_progress_callback(self, mock_run, mock_which, tmp_path):
        ipsw = tmp_path / "fw.ipsw"
        ipsw.touch()
        blob = tmp_path / "blob.shsh2"
        blob.write_text("blob_data")

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Done", stderr=""
        )
        cb = MagicMock()
        run_futurerestore("abc123", ipsw, blob, progress_cb=cb)
        assert cb.call_count >= 1
```

**Step 2: Run tests — expect FAIL**

**Step 3: Create `app/services/futurerestore.py`**

```python
"""FutureRestore service — iOS downgrade/upgrade using saved SHSH blobs.

Wraps the futurerestore binary. Requires device in recovery/DFU mode,
a valid SHSH2 blob, and a compatible IPSW firmware file.
"""

import json
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from app.models.tools import BypassResult, RestoreCompatibility

logger = logging.getLogger(__name__)

_TOOL_TIMEOUT = 1800  # 30 minutes for full restore


def check_futurerestore_available() -> bool:
    """Check if futurerestore binary is available in PATH."""
    return shutil.which("futurerestore") is not None


def check_compatibility(
    device_model: str,
    target_version: str,
    blob_path: Path,
) -> RestoreCompatibility:
    """Check if a FutureRestore is possible with the given blob.

    Validates the blob file exists and contains data. Full SEP compatibility
    checking requires querying Apple's TSS server (best-effort here).
    """
    if not blob_path.exists():
        return RestoreCompatibility(
            compatible=False,
            target_version=target_version,
            blob_valid=False,
            sep_compatible=False,
            reason="SHSH2 blob file not found",
        )

    content = blob_path.read_text(errors="replace").strip()
    if not content:
        return RestoreCompatibility(
            compatible=False,
            target_version=target_version,
            blob_valid=False,
            sep_compatible=False,
            reason="SHSH2 blob file is empty",
        )

    # Basic validation: check if it looks like a plist/JSON blob
    blob_valid = "ApImg4Ticket" in content or "generator" in content

    # SEP compatibility is hard to determine statically — assume compatible
    # unless we have evidence otherwise. In practice, futurerestore will
    # check this at runtime and fail fast if incompatible.
    return RestoreCompatibility(
        compatible=blob_valid,
        target_version=target_version,
        blob_valid=blob_valid,
        sep_compatible=True,  # Optimistic; futurerestore verifies at runtime
        reason=None if blob_valid else "Blob does not contain ApImg4Ticket or generator",
    )


def run_futurerestore(
    udid: str,
    ipsw_path: Path,
    blob_path: Path,
    set_nonce: bool = True,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> BypassResult:
    """Run FutureRestore to downgrade/upgrade iOS.

    Device must be in recovery or DFU mode. Use firmware_manager helpers first.
    """
    if not check_futurerestore_available():
        return BypassResult(
            success=False,
            tool="checkra1n",  # Reuses BypassResult; tool field is informational
            error="not_available",
            message="futurerestore binary not found in PATH",
            timestamp=datetime.now(),
        )

    cmd = [
        "futurerestore",
        "-t", str(blob_path),
        "--latest-sep",
        "--latest-baseband",
    ]
    if set_nonce:
        cmd.append("--set-nonce")
    cmd.append(str(ipsw_path))

    if progress_cb:
        progress_cb("Starting FutureRestore...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_TOOL_TIMEOUT,
        )
        if progress_cb:
            progress_cb("FutureRestore finished")

        if result.returncode == 0:
            return BypassResult(
                success=True,
                tool="checkra1n",
                message=result.stdout.strip() or "Restore successful",
                timestamp=datetime.now(),
            )
        return BypassResult(
            success=False,
            tool="checkra1n",
            error="process_error",
            message=result.stderr.strip() or f"Exit code {result.returncode}",
            timestamp=datetime.now(),
        )
    except subprocess.TimeoutExpired:
        logger.error("FutureRestore timed out for %s", udid)
        return BypassResult(
            success=False,
            tool="checkra1n",
            error="timeout",
            message=f"Timed out after {_TOOL_TIMEOUT}s",
            timestamp=datetime.now(),
        )
    except Exception as e:
        logger.error("FutureRestore failed for %s: %s", udid, e)
        return BypassResult(
            success=False,
            tool="checkra1n",
            error="exception",
            message=str(e),
            timestamp=datetime.now(),
        )
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add app/services/futurerestore.py tests/test_futurerestore.py
git commit -m "feat(sprint5): add FutureRestore downgrade service"
```

---

## Task 4: Syslog Service — `app/services/syslog_service.py`

**Files:**
- Create: `app/services/syslog_service.py`
- Test: `tests/test_syslog_service.py`

**Step 1: Write tests**

Create `tests/test_syslog_service.py`:

```python
"""Tests for syslog streaming service."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from app.models.tools import SyslogEntry, SyslogFilter
from app.services.syslog_service import (
    SyslogBuffer,
    filter_entry,
    parse_syslog_line,
)


class TestParseSyslogLine:
    def test_standard_line(self):
        line = "Mar  2 10:30:45 iPhone kernel[0]: panic - loss of connectivity"
        entry = parse_syslog_line(line)
        assert entry is not None
        assert entry.process == "kernel"
        assert entry.pid == 0
        assert "panic" in entry.message

    def test_process_with_pid(self):
        line = "Mar  2 10:30:45 iPhone SpringBoard[42]: Application launched"
        entry = parse_syslog_line(line)
        assert entry is not None
        assert entry.process == "SpringBoard"
        assert entry.pid == 42

    def test_malformed_line(self):
        entry = parse_syslog_line("not a syslog line at all")
        assert entry is None

    def test_empty_line(self):
        entry = parse_syslog_line("")
        assert entry is None


class TestFilterEntry:
    def _make_entry(self, process="SpringBoard", level="Info", message="test"):
        return SyslogEntry(
            timestamp=datetime.now(),
            process=process,
            pid=1,
            level=level,
            message=message,
        )

    def test_no_filter(self):
        entry = self._make_entry()
        assert filter_entry(entry, SyslogFilter()) is True

    def test_process_filter_match(self):
        entry = self._make_entry(process="kernel")
        assert filter_entry(entry, SyslogFilter(process="kernel")) is True

    def test_process_filter_no_match(self):
        entry = self._make_entry(process="kernel")
        assert filter_entry(entry, SyslogFilter(process="SpringBoard")) is False

    def test_level_filter(self):
        entry = self._make_entry(level="Error")
        assert filter_entry(entry, SyslogFilter(level="Error")) is True
        assert filter_entry(entry, SyslogFilter(level="Warning")) is False

    def test_keyword_filter(self):
        entry = self._make_entry(message="camera hardware panic detected")
        assert filter_entry(entry, SyslogFilter(keyword="panic")) is True
        assert filter_entry(entry, SyslogFilter(keyword="wifi")) is False

    def test_keyword_case_insensitive(self):
        entry = self._make_entry(message="Kernel PANIC")
        assert filter_entry(entry, SyslogFilter(keyword="panic")) is True

    def test_combined_filters(self):
        entry = self._make_entry(process="kernel", level="Error", message="panic")
        f = SyslogFilter(process="kernel", level="Error", keyword="panic")
        assert filter_entry(entry, f) is True

    def test_combined_partial_mismatch(self):
        entry = self._make_entry(process="kernel", level="Info", message="ok")
        f = SyslogFilter(process="kernel", level="Error")
        assert filter_entry(entry, f) is False


class TestSyslogBuffer:
    def test_add_and_get(self):
        buf = SyslogBuffer(max_size=5)
        for i in range(3):
            buf.add(self._make_entry(message=f"msg{i}"))
        entries = buf.get_all()
        assert len(entries) == 3
        assert entries[0].message == "msg0"

    def test_overflow(self):
        buf = SyslogBuffer(max_size=3)
        for i in range(5):
            buf.add(self._make_entry(message=f"msg{i}"))
        entries = buf.get_all()
        assert len(entries) == 3
        assert entries[0].message == "msg2"  # oldest kept

    def test_clear(self):
        buf = SyslogBuffer(max_size=10)
        buf.add(self._make_entry())
        buf.clear()
        assert len(buf.get_all()) == 0

    def _make_entry(self, message="test"):
        return SyslogEntry(
            timestamp=datetime.now(),
            process="test",
            pid=1,
            level="Info",
            message=message,
        )
```

**Step 2: Run tests — expect FAIL**

**Step 3: Create `app/services/syslog_service.py`**

```python
"""Real-time iOS syslog streaming via pymobiledevice3.

Provides parsing, filtering, buffering, and an async generator for WebSocket streaming.
"""

import logging
import re
from collections import deque
from datetime import datetime
from typing import Optional

from app.models.tools import SyslogEntry, SyslogFilter

logger = logging.getLogger(__name__)

# Syslog line format: "Mon DD HH:MM:SS hostname process[pid]: message"
_SYSLOG_RE = re.compile(
    r"^(\w+\s+\d+\s+[\d:]+)\s+\S+\s+(\w[\w.-]*)(?:\[(\d+)\])?:\s*(.*)$"
)

# Map common syslog keywords to levels
_LEVEL_KEYWORDS = {
    "Emergency": ["panic", "emergency"],
    "Alert": ["alert"],
    "Critical": ["critical", "fatal"],
    "Error": ["error", "fail", "exception"],
    "Warning": ["warn"],
    "Notice": ["notice"],
    "Debug": ["debug"],
}


def parse_syslog_line(line: str) -> Optional[SyslogEntry]:
    """Parse a raw syslog line into a SyslogEntry.

    Returns None if the line can't be parsed.
    """
    if not line or not line.strip():
        return None

    match = _SYSLOG_RE.match(line.strip())
    if not match:
        return None

    time_str, process, pid_str, message = match.groups()

    # Parse timestamp — syslog doesn't include year, use current
    try:
        ts = datetime.strptime(f"{datetime.now().year} {time_str}", "%Y %b %d %H:%M:%S")
    except ValueError:
        ts = datetime.now()

    pid = int(pid_str) if pid_str else 0

    # Infer level from message content
    level = _infer_level(message)

    return SyslogEntry(
        timestamp=ts,
        process=process,
        pid=pid,
        level=level,
        message=message,
    )


def _infer_level(message: str) -> str:
    """Infer log level from message content."""
    lower = message.lower()
    for level, keywords in _LEVEL_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return level
    return "Info"


def filter_entry(entry: SyslogEntry, filt: SyslogFilter) -> bool:
    """Check if a syslog entry matches the given filter."""
    if filt.process and entry.process != filt.process:
        return False
    if filt.level and entry.level != filt.level:
        return False
    if filt.keyword and filt.keyword.lower() not in entry.message.lower():
        return False
    return True


class SyslogBuffer:
    """Fixed-size buffer for recent syslog entries."""

    def __init__(self, max_size: int = 1000):
        self._entries: deque[SyslogEntry] = deque(maxlen=max_size)

    def add(self, entry: SyslogEntry) -> None:
        self._entries.append(entry)

    def get_all(self) -> list[SyslogEntry]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()


def create_syslog_stream(udid: Optional[str] = None):
    """Create a syslog stream generator from a connected device.

    Uses pymobiledevice3's OsTraceService. Returns a generator yielding raw lines.
    On import error or connection failure, yields nothing.
    """
    try:
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.services.os_trace import OsTraceService

        lockdown = create_using_usbmux(serial=udid)
        service = OsTraceService(lockdown)
        yield from service.syslog()
    except ImportError:
        logger.error("pymobiledevice3 not available for syslog streaming")
    except Exception as e:
        logger.error("Failed to start syslog stream for %s: %s", udid, e)
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add app/services/syslog_service.py tests/test_syslog_service.py
git commit -m "feat(sprint5): add syslog streaming service with parsing, filtering, buffering"
```

---

## Task 5: Cable Check — extend `app/services/diagnostic_engine.py`

**Files:**
- Modify: `app/services/diagnostic_engine.py` — add `check_cable_quality()` after `_get_storage()`
- Modify: `app/models/diagnostic.py` — add `CableCheckResult` model (or import from tools.py)
- Test: `tests/test_cable_check.py`

**Step 1: Write tests**

Create `tests/test_cable_check.py`:

```python
"""Tests for USB cable quality check."""

from unittest.mock import MagicMock

from app.models.tools import CableCheckResult
from app.services.diagnostic_engine import check_cable_quality


class TestCableCheck:
    def test_usb3_good_cable(self):
        lockdown = MagicMock()
        lockdown.get_value.side_effect = lambda domain=None, key=None: {
            ("com.apple.mobile.battery", None): {"ExternalChargeCapable": True},
            (None, "ConnectionSpeed"): 480000000,
            (None, "ConnectionType"): "USB",
        }.get((domain, key), None)

        result = check_cable_quality(lockdown)
        assert isinstance(result, CableCheckResult)
        assert result.charge_capable is True
        assert result.data_capable is True
        assert len(result.warnings) == 0

    def test_no_charge_capability(self):
        lockdown = MagicMock()
        lockdown.get_value.side_effect = lambda domain=None, key=None: {
            ("com.apple.mobile.battery", None): {"ExternalChargeCapable": False},
            (None, "ConnectionSpeed"): 480000000,
            (None, "ConnectionType"): "USB",
        }.get((domain, key), None)

        result = check_cable_quality(lockdown)
        assert result.charge_capable is False
        assert any("charge" in w.lower() for w in result.warnings)

    def test_low_speed_cable(self):
        lockdown = MagicMock()
        lockdown.get_value.side_effect = lambda domain=None, key=None: {
            ("com.apple.mobile.battery", None): {"ExternalChargeCapable": True},
            (None, "ConnectionSpeed"): 12000000,  # USB 1.1 speed
            (None, "ConnectionType"): "USB",
        }.get((domain, key), None)

        result = check_cable_quality(lockdown)
        assert "slow" in result.connection_type.lower() or len(result.warnings) > 0

    def test_missing_properties(self):
        lockdown = MagicMock()
        lockdown.get_value.return_value = None

        result = check_cable_quality(lockdown)
        assert result.connection_type == "Unknown"
        assert result.data_capable is True  # We're connected, so data works

    def test_exception_handling(self):
        lockdown = MagicMock()
        lockdown.get_value.side_effect = Exception("Device disconnected")

        result = check_cable_quality(lockdown)
        assert result.connection_type == "Unknown"
        assert len(result.warnings) > 0
```

**Step 2: Run tests — expect FAIL**

**Step 3: Add `check_cable_quality()` to `app/services/diagnostic_engine.py`**

Add at end of file:

```python
def check_cable_quality(lockdown: Any) -> "CableCheckResult":
    """Check USB cable quality based on connection properties.

    Not a full MFi authenticity check — detects poor/fake cables via
    low negotiated speed or missing charge capability.
    """
    from app.models.tools import CableCheckResult

    warnings: list[str] = []
    connection_type = "Unknown"
    charge_capable = False
    data_capable = True  # If we're connected, data works
    negotiated_speed = None

    try:
        # Check charge capability
        battery_info = lockdown.get_value(domain="com.apple.mobile.battery")
        if battery_info and isinstance(battery_info, dict):
            charge_capable = battery_info.get("ExternalChargeCapable", False)
            if not charge_capable:
                warnings.append("Cable does not support charging — possible data-only or damaged cable")
        else:
            charge_capable = False

        # Check connection speed
        speed = lockdown.get_value(key="ConnectionSpeed")
        if speed and isinstance(speed, (int, float)):
            if speed >= 480_000_000:
                connection_type = "USB 2.0 High-Speed"
                negotiated_speed = f"{speed / 1_000_000:.0f} Mbps"
            elif speed >= 5_000_000_000:
                connection_type = "USB 3.0 SuperSpeed"
                negotiated_speed = f"{speed / 1_000_000_000:.1f} Gbps"
            elif speed >= 12_000_000:
                connection_type = "USB 1.1 Full-Speed (slow)"
                negotiated_speed = f"{speed / 1_000_000:.0f} Mbps"
                warnings.append("Low USB speed detected — possible poor quality cable")
            else:
                connection_type = "USB Low-Speed"
                negotiated_speed = f"{speed / 1_000:.0f} Kbps"
                warnings.append("Very low USB speed — cable may be damaged or non-MFi")

    except Exception as e:
        logger.warning("Cable check failed: %s", e)
        warnings.append(f"Could not read cable properties: {e}")

    return CableCheckResult(
        connection_type=connection_type,
        charge_capable=charge_capable,
        data_capable=data_capable,
        negotiated_speed=negotiated_speed,
        warnings=warnings,
    )
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add app/services/diagnostic_engine.py tests/test_cable_check.py
git commit -m "feat(sprint5): add USB cable quality check to diagnostic engine"
```

---

## Task 6: Tools API Router — `app/api/tools.py`

**Files:**
- Create: `app/api/tools.py`
- Modify: `app/main.py` — register new router
- Test: `tests/test_tools_api.py`

**Step 1: Write tests**

Create `tests/test_tools_api.py`:

```python
"""Tests for tools API endpoints — bypass, futurerestore, cable check, availability."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestToolsAvailability:
    @patch("app.services.bypass_tools.check_checkra1n_available", return_value=True)
    @patch("app.services.bypass_tools.check_broque_available", return_value=False)
    @patch("app.services.bypass_tools.check_ssh_ramdisk_available", return_value=True)
    @patch("app.services.futurerestore.check_futurerestore_available", return_value=False)
    def test_availability_endpoint(self, *mocks):
        resp = client.get("/api/tools/availability")
        assert resp.status_code == 200
        data = resp.json()
        assert data["checkra1n"] is True
        assert data["broque"] is False
        assert data["ssh_ramdisk"] is True
        assert data["futurerestore"] is False


class TestCheckra1nEndpoint:
    @patch("app.services.bypass_tools.run_checkra1n")
    def test_success(self, mock_run):
        from app.models.tools import BypassResult
        mock_run.return_value = BypassResult(success=True, tool="checkra1n", message="Done")
        resp = client.post("/api/tools/checkra1n/abc123")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.services.bypass_tools.run_checkra1n")
    def test_not_available(self, mock_run):
        from app.models.tools import BypassResult
        mock_run.return_value = BypassResult(
            success=False, tool="checkra1n", error="not_available"
        )
        resp = client.post("/api/tools/checkra1n/abc123")
        assert resp.status_code == 200
        assert resp.json()["success"] is False


class TestBroqueEndpoint:
    @patch("app.services.bypass_tools.run_broque_bypass")
    def test_success(self, mock_run):
        from app.models.tools import BypassResult
        mock_run.return_value = BypassResult(success=True, tool="broque", message="Bypassed")
        resp = client.post("/api/tools/broque/abc123")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestSSHRamdiskEndpoint:
    @patch("app.services.bypass_tools.boot_ssh_ramdisk")
    def test_boot(self, mock_boot):
        from app.models.tools import BypassResult
        mock_boot.return_value = BypassResult(success=True, tool="ssh_ramdisk")
        resp = client.post("/api/tools/ssh-ramdisk/abc123")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.services.bypass_tools.extract_data")
    def test_extract(self, mock_extract):
        mock_extract.return_value = {"photos": {"success": True, "count": 42, "message": "ok"}}
        resp = client.post(
            "/api/tools/ssh-ramdisk/abc123/extract",
            json={"data_types": ["photos"], "target_dir": "/tmp/out"},
        )
        assert resp.status_code == 200
        assert resp.json()["photos"]["success"] is True


class TestFutureRestoreEndpoint:
    @patch("app.services.futurerestore.check_compatibility")
    def test_check(self, mock_check):
        from app.models.tools import RestoreCompatibility
        mock_check.return_value = RestoreCompatibility(
            compatible=True, target_version="15.4.1", blob_valid=True, sep_compatible=True
        )
        resp = client.get("/api/tools/futurerestore/abc123/check?target_version=15.4.1&blob_path=/tmp/b.shsh2")
        assert resp.status_code == 200
        assert resp.json()["compatible"] is True

    @patch("app.services.futurerestore.run_futurerestore")
    def test_restore(self, mock_run):
        from app.models.tools import BypassResult
        mock_run.return_value = BypassResult(success=True, tool="checkra1n", message="Restored")
        resp = client.post(
            "/api/tools/futurerestore/abc123",
            json={"ipsw_path": "/tmp/fw.ipsw", "blob_path": "/tmp/b.shsh2"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestCableCheckEndpoint:
    @patch("app.services.diagnostic_engine.check_cable_quality")
    @patch("app.services.device_service.create_lockdown")
    def test_cable_check(self, mock_lockdown, mock_cable):
        from app.models.tools import CableCheckResult
        mock_lockdown.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_lockdown.return_value.__exit__ = MagicMock(return_value=False)
        mock_cable.return_value = CableCheckResult(
            connection_type="USB 2.0 High-Speed",
            charge_capable=True,
            data_capable=True,
        )
        resp = client.get("/api/tools/cable/abc123")
        assert resp.status_code == 200
        assert resp.json()["connection_type"] == "USB 2.0 High-Speed"
```

**Step 2: Run tests — expect FAIL**

**Step 3: Create `app/api/tools.py`**

```python
"""API router for Sprint 5 tools — bypass, futurerestore, cable check, syslog."""

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.tools import BypassResult, CableCheckResult, RestoreCompatibility
from app.services import bypass_tools, diagnostic_engine, futurerestore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


# ── Request models ─────────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    data_types: list[str]
    target_dir: str


class FutureRestoreRequest(BaseModel):
    ipsw_path: str
    blob_path: str
    set_nonce: bool = True


# ── Availability ───────────────────────────────────────────────────────

@router.get("/availability")
async def check_availability() -> dict:
    """Check which bypass/recovery tools are installed."""
    return {
        "checkra1n": bypass_tools.check_checkra1n_available(),
        "broque": bypass_tools.check_broque_available(),
        "ssh_ramdisk": bypass_tools.check_ssh_ramdisk_available(),
        "futurerestore": futurerestore.check_futurerestore_available(),
    }


# ── checkra1n ──────────────────────────────────────────────────────────

@router.post("/checkra1n/{udid}")
async def run_checkra1n(udid: str) -> dict:
    """Run checkra1n jailbreak on device. Device must be in DFU mode."""
    result = await asyncio.to_thread(bypass_tools.run_checkra1n, udid)
    return result.model_dump()


# ── Broque Ramdisk ─────────────────────────────────────────────────────

@router.post("/broque/{udid}")
async def run_broque(udid: str) -> dict:
    """Run Broque Ramdisk iCloud bypass. Device must be in DFU mode."""
    result = await asyncio.to_thread(bypass_tools.run_broque_bypass, udid)
    return result.model_dump()


# ── SSH Ramdisk ────────────────────────────────────────────────────────

@router.post("/ssh-ramdisk/{udid}")
async def boot_ssh_ramdisk(udid: str) -> dict:
    """Boot SSH ramdisk for data extraction."""
    result = await asyncio.to_thread(bypass_tools.boot_ssh_ramdisk, udid)
    return result.model_dump()


@router.post("/ssh-ramdisk/{udid}/extract")
async def extract_data(udid: str, req: ExtractRequest) -> dict:
    """Extract data from device via SSH ramdisk."""
    result = await asyncio.to_thread(
        bypass_tools.extract_data, udid, Path(req.target_dir), req.data_types
    )
    return result


# ── FutureRestore ──────────────────────────────────────────────────────

@router.get("/futurerestore/{udid}/check")
async def check_futurerestore_compat(
    udid: str, target_version: str, blob_path: str
) -> dict:
    """Check if FutureRestore is compatible with given blob."""
    result = futurerestore.check_compatibility(
        device_model=udid,  # Will be resolved to model in service
        target_version=target_version,
        blob_path=Path(blob_path),
    )
    return result.model_dump()


@router.post("/futurerestore/{udid}")
async def run_futurerestore_endpoint(udid: str, req: FutureRestoreRequest) -> dict:
    """Run FutureRestore downgrade/upgrade."""
    result = await asyncio.to_thread(
        futurerestore.run_futurerestore,
        udid,
        Path(req.ipsw_path),
        Path(req.blob_path),
        req.set_nonce,
    )
    return result.model_dump()


# ── Cable Check ────────────────────────────────────────────────────────

@router.get("/cable/{udid}")
async def check_cable(udid: str) -> dict:
    """Check USB cable quality for connected device."""
    try:
        from app.services.device_service import create_lockdown
        with create_lockdown(udid) as lockdown:
            result = diagnostic_engine.check_cable_quality(lockdown)
            return result.model_dump()
    except Exception as e:
        logger.error("Cable check failed for %s: %s", udid, e)
        raise HTTPException(status_code=500, detail=str(e))
```

**Step 4: Register router in `app/main.py`**

Add import at line ~24: `from app.api import tools`
Add router at line ~59: `app.include_router(tools.router)`

**Step 5: Run tests — expect PASS**

```bash
pytest tests/test_tools_api.py -v
```

**Step 6: Commit**

```bash
git add app/api/tools.py tests/test_tools_api.py app/main.py
git commit -m "feat(sprint5): add tools API router — bypass, futurerestore, cable check"
```

---

## Task 7: Syslog WebSocket — extend `app/api/websocket.py`

**Files:**
- Modify: `app/api/websocket.py` — add `/ws/syslog/{udid}` endpoint
- Modify: `app/main.py` — start syslog background infrastructure if needed
- Test: `tests/test_syslog_ws.py`

**Step 1: Write tests**

Create `tests/test_syslog_ws.py`:

```python
"""Tests for syslog WebSocket endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


class TestSyslogWebSocket:
    @patch("app.services.syslog_service.create_syslog_stream")
    def test_syslog_ws_connect(self, mock_stream):
        """Test that syslog WebSocket accepts connections."""
        mock_stream.return_value = iter([
            "Mar  2 10:30:45 iPhone kernel[0]: test message",
        ])
        client = TestClient(app)
        with client.websocket_connect("/ws/syslog/abc123") as ws:
            # Send a filter
            ws.send_json({"process": None, "level": None, "keyword": None})
            # Should receive the parsed entry
            data = ws.receive_json()
            assert data["event"] == "syslog"
            assert data["data"]["process"] == "kernel"
```

**Step 2: Run tests — expect FAIL**

**Step 3: Add syslog WebSocket endpoint to `app/api/websocket.py`**

Add after the existing `websocket_endpoint` function:

```python
@router.websocket("/ws/syslog/{udid}")
async def syslog_websocket(ws: WebSocket, udid: str) -> None:
    """Stream real-time syslog from a device over WebSocket."""
    from app.models.tools import SyslogFilter
    from app.services.syslog_service import (
        SyslogBuffer,
        create_syslog_stream,
        filter_entry,
        parse_syslog_line,
    )

    await ws.accept()
    logger.info("Syslog WebSocket connected for device %s", udid)

    buf = SyslogBuffer(max_size=1000)
    current_filter = SyslogFilter()

    try:
        # Wait for initial filter from client
        try:
            data = await asyncio.wait_for(ws.receive_text(), timeout=5.0)
            msg = json.loads(data)
            current_filter = SyslogFilter(**msg)
        except (asyncio.TimeoutError, Exception):
            pass  # Use default empty filter

        # Stream syslog in a background thread
        def _stream():
            for line in create_syslog_stream(udid):
                entry = parse_syslog_line(str(line))
                if entry:
                    buf.add(entry)
                    if filter_entry(entry, current_filter):
                        yield entry

        stream_gen = await asyncio.to_thread(lambda: list(create_syslog_stream(udid)))
        for raw_line in stream_gen:
            entry = parse_syslog_line(str(raw_line))
            if entry and filter_entry(entry, current_filter):
                await ws.send_text(json.dumps({
                    "event": "syslog",
                    "data": entry.model_dump(mode="json"),
                }))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("Syslog WebSocket error for %s: %s", udid, e)
    finally:
        logger.info("Syslog WebSocket disconnected for device %s", udid)
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add app/api/websocket.py tests/test_syslog_ws.py
git commit -m "feat(sprint5): add syslog WebSocket streaming endpoint"
```

---

## Task 8: Error Handling Hardening

**Files:**
- Modify: `app/main.py` — add global exception handler
- Modify: `app/services/verification_service.py` — add offline fallback
- Create: `app/utils/resilience.py` — `@with_fallback` decorator
- Test: `tests/test_resilience.py`

**Step 1: Write tests**

Create `tests/test_resilience.py`:

```python
"""Tests for error handling and resilience utilities."""

from unittest.mock import MagicMock, patch

from app.utils.resilience import with_fallback


class TestWithFallback:
    def test_normal_execution(self):
        @with_fallback(default="fallback_value")
        def good_func():
            return "success"
        assert good_func() == "success"

    def test_fallback_on_exception(self):
        @with_fallback(default="fallback_value")
        def bad_func():
            raise ConnectionError("offline")
        assert bad_func() == "fallback_value"

    def test_fallback_with_logger(self):
        @with_fallback(default=None, log_message="API call failed")
        def bad_func():
            raise TimeoutError("timeout")
        assert bad_func() is None

    def test_fallback_preserves_args(self):
        @with_fallback(default={})
        def func_with_args(a, b, key=None):
            raise RuntimeError("nope")
        assert func_with_args(1, 2, key="test") == {}

    def test_no_fallback_for_programming_errors(self):
        """TypeError and ValueError should NOT be caught — they're bugs."""
        @with_fallback(default="fallback")
        def buggy_func():
            raise TypeError("wrong type")
        # Programming errors should propagate
        import pytest
        with pytest.raises(TypeError):
            buggy_func()
```

**Step 2: Run tests — expect FAIL**

**Step 3: Create `app/utils/resilience.py`**

```python
"""Resilience utilities for graceful degradation."""

import functools
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Exceptions that indicate infrastructure/network issues (should fallback)
_TRANSIENT_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
    IOError,
)


def with_fallback(default: Any = None, log_message: str = ""):
    """Decorator that returns a default value on transient failures.

    Programming errors (TypeError, ValueError, KeyError) are NOT caught
    because they indicate bugs that should be fixed, not retried.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except _TRANSIENT_EXCEPTIONS as e:
                msg = log_message or f"{func.__name__} failed"
                logger.warning("%s: %s", msg, e)
                return default
        return wrapper
    return decorator
```

**Step 4: Add global exception handler to `app/main.py`**

Add after app instantiation:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "An unexpected error occurred"},
    )
```

**Step 5: Run tests — expect PASS**

**Step 6: Commit**

```bash
git add app/utils/resilience.py tests/test_resilience.py app/main.py
git commit -m "feat(sprint5): add error handling hardening — fallback decorator + global handler"
```

---

## Task 9: USB Build Script — `scripts/build_usb.sh`

**Files:**
- Create: `scripts/build_usb.sh`

**Step 1: Create the build script**

```bash
#!/usr/bin/env bash
# build_usb.sh — Build a reproducible Ubuntu 24.04 live USB image with iDiag pre-installed.
#
# Requirements: Run on a Debian/Ubuntu host with sudo access.
# Usage: sudo bash scripts/build_usb.sh [output_dir]
#
# Output: idiag-live.iso in the output directory (default: ./build/)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${1:-$PROJECT_ROOT/build}"
WORK_DIR="$OUTPUT_DIR/work"
IMAGE_NAME="idiag-live"

echo "=== iDiag Live USB Builder ==="
echo "Project root: $PROJECT_ROOT"
echo "Output dir:   $OUTPUT_DIR"

# ── Prerequisites ──────────────────────────────────────────────────────

check_deps() {
    local missing=()
    for cmd in debootstrap lb mksquashfs xorriso; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "Installing missing build dependencies..."
        apt-get update -qq
        apt-get install -y -qq live-build debootstrap squashfs-tools xorriso
    fi
}

check_deps

# ── Configure live-build ───────────────────────────────────────────────

mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

lb config \
    --distribution noble \
    --architectures amd64 \
    --binary-images iso-hybrid \
    --bootloaders syslinux,grub-efi \
    --debian-installer false \
    --memtest none \
    --iso-application "iDiag" \
    --iso-volume "iDiag Live" \
    2>/dev/null || true

# ── Package lists ──────────────────────────────────────────────────────

mkdir -p config/package-lists

cat > config/package-lists/idiag.list.chroot <<'PACKAGES'
python3
python3-pip
python3-venv
usbmuxd
libimobiledevice-utils
libimobiledevice6
libusbmuxd-tools
ideviceinstaller
git
wget
curl
openssh-client
sqlite3
libpango-1.0-0
libharfbuzz0b
libffi-dev
libgdk-pixbuf2.0-0
libcairo2
libgirepository1.0-dev
gir1.2-webkit2-4.1
PACKAGES

# ── Custom hooks ───────────────────────────────────────────────────────

mkdir -p config/hooks/normal

cat > config/hooks/normal/0100-install-idiag.hook.chroot <<'HOOK'
#!/bin/bash
set -e

# Create idiag user
useradd -m -s /bin/bash idiag || true
echo "idiag:idiag" | chpasswd

# Install Python packages
pip3 install --break-system-packages \
    fastapi uvicorn[standard] pymobiledevice3 pywebview httpx \
    pydantic jinja2 weasyprint qrcode[pil]

# Copy iDiag application
mkdir -p /opt/idiag
echo "iDiag application files will be copied here during USB creation"

# Install checkra1n (if available for the target platform)
if ! command -v checkra1n &>/dev/null; then
    echo "NOTE: checkra1n must be manually added to /usr/local/bin/"
fi

# Install futurerestore
if ! command -v futurerestore &>/dev/null; then
    echo "NOTE: futurerestore must be manually added to /usr/local/bin/"
fi

# udev rules for iPhone hotplug
cat > /etc/udev/rules.d/39-libimobiledevice.rules <<'UDEV'
# Apple iOS devices
SUBSYSTEM=="usb", ATTR{idVendor}=="05ac", ATTR{idProduct}=="12a8", MODE="0666"
SUBSYSTEM=="usb", ATTR{idVendor}=="05ac", ATTR{idProduct}=="12ab", MODE="0666"
UDEV

# Auto-start iDiag on login
mkdir -p /home/idiag/.config/autostart
cat > /home/idiag/.config/autostart/idiag.desktop <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=iDiag
Exec=/opt/idiag/start.sh
Terminal=false
Hidden=false
DESKTOP
chown -R idiag:idiag /home/idiag/.config
HOOK

chmod +x config/hooks/normal/0100-install-idiag.hook.chroot

# ── Copy application files ─────────────────────────────────────────────

mkdir -p config/includes.chroot/opt/idiag

# Copy project files (excluding dev files)
rsync -a --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
    --exclude='build' --exclude='*.pyc' --exclude='node_modules' \
    "$PROJECT_ROOT/" config/includes.chroot/opt/idiag/

# Create start script
cat > config/includes.chroot/opt/idiag/start.sh <<'START'
#!/bin/bash
cd /opt/idiag
python3 -m app.main
START
chmod +x config/includes.chroot/opt/idiag/start.sh

# ── Build ──────────────────────────────────────────────────────────────

echo "Building live image (this may take 10-30 minutes)..."
lb build 2>&1 | tee "$OUTPUT_DIR/build.log"

# ── Output ─────────────────────────────────────────────────────────────

ISO_FILE=$(find . -name "*.iso" -type f | head -1)
if [[ -n "$ISO_FILE" ]]; then
    mv "$ISO_FILE" "$OUTPUT_DIR/$IMAGE_NAME.iso"
    echo ""
    echo "=== Build complete ==="
    echo "ISO: $OUTPUT_DIR/$IMAGE_NAME.iso"
    echo "Size: $(du -h "$OUTPUT_DIR/$IMAGE_NAME.iso" | cut -f1)"
    echo ""
    echo "Write to USB: sudo dd if=$OUTPUT_DIR/$IMAGE_NAME.iso of=/dev/sdX bs=4M status=progress"
else
    echo "ERROR: No ISO file found. Check $OUTPUT_DIR/build.log"
    exit 1
fi
```

**Step 2: Commit (no automated tests for build script — it requires root + debootstrap)**

```bash
git add scripts/build_usb.sh
git commit -m "feat(sprint5): add reproducible USB live image build script"
```

---

## Task 10: Syslog UI Panel — extend `app/templates/index.html`

**Files:**
- Modify: `app/templates/index.html` — add syslog viewer tab/panel

**Step 1: Add syslog panel to dashboard**

Add a new tab in the dashboard navigation and a syslog panel with:
- Terminal-style dark background
- Process filter dropdown
- Level filter (Emergency through Debug)
- Keyword search input
- Auto-scroll toggle button
- Log entry display area with color-coded levels
- WebSocket connection to `/ws/syslog/{udid}`

The JS should:
1. Connect to `/ws/syslog/{currentUdid}` when the syslog tab is opened
2. Send filter JSON on connection and on filter change
3. Parse incoming `{"event": "syslog", "data": {...}}` messages
4. Append formatted entries to the log area
5. Auto-scroll to bottom unless paused
6. Color-code by level (red=Error/Critical, yellow=Warning, white=Info, gray=Debug)

**Step 2: Run full test suite to confirm no regressions**

```bash
pytest tests/ -v
```

**Step 3: Commit**

```bash
git add app/templates/index.html
git commit -m "feat(sprint5): add syslog viewer panel to dashboard"
```

---

## Task 11: Final Integration & Full Test Run

**Step 1: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All existing 177+ tests pass, plus all new Sprint 5 tests.

**Step 2: Verify all new endpoints respond**

Manually verify (or add integration test):
- `GET /api/tools/availability` returns tool status
- `GET /api/tools/cable/{udid}` returns cable info
- `POST /api/tools/checkra1n/{udid}` returns bypass result
- `WS /ws/syslog/{udid}` accepts connection

**Step 3: Final commit if any fixups needed**

```bash
git add -A
git commit -m "feat(sprint5): Sprint 5 complete — bypass tools, syslog, cable check, USB build"
```
