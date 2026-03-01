# Sprint 5: Edge Cases & Hardening — Design

## Date: 2026-03-02
## Status: Approved

---

## Overview

Sprint 5 adds bypass/recovery tools for edge-case devices, a real-time syslog viewer, USB cable quality checking, error handling hardening across the codebase, and a reproducible bootable USB build script. All bypass tools use subprocess wrappers with stub mode for non-Linux development.

---

## New Files

```
app/services/bypass_tools.py      — checkra1n, Broque Ramdisk, SSH Ramdisk wrappers
app/services/futurerestore.py     — FutureRestore downgrade service
app/services/syslog_service.py    — Real-time syslog streaming via pymobiledevice3
app/api/tools.py                  — API router for bypass tools, syslog, cable check
app/models/tools.py               — Pydantic models for bypass/syslog/cable results
scripts/build_usb.sh              — Reproducible Ubuntu 24.04 live USB builder
tests/test_bypass_tools.py
tests/test_futurerestore.py
tests/test_syslog_service.py
tests/test_tools_api.py
```

---

## Feature 1: Bypass Tools (`bypass_tools.py`)

Three subprocess wrappers following the `firmware_manager.py` pattern (stateless functions, optional progress callbacks, Optional returns).

### checkra1n
Jailbreaks A5-A11 devices (iPhone 5s–iPhone X) for diagnostic access on iOS 12.0–14.8.1.

- `check_checkra1n_available() -> bool` — binary in PATH check
- `run_checkra1n(udid: str, cli_mode: bool = True, progress_cb: Optional[Callable]) -> BypassResult` — runs `checkra1n -c` as subprocess, streams stdout for progress

### Broque Ramdisk
iCloud bypass for A9-A11 devices.

- `check_broque_available() -> bool` — checks for cloned repo + dependencies
- `run_broque_bypass(udid: str, progress_cb: Optional[Callable]) -> BypassResult` — runs Broque Ramdisk script sequence (boot ramdisk, mount data, patch activation)
- Requires device in DFU mode first (reuses `enter_dfu_mode()` from firmware_manager)

### SSH Ramdisk
Data extraction from passcode-locked A9-A11 devices.

- `boot_ssh_ramdisk(udid: str, progress_cb: Optional[Callable]) -> BypassResult` — boots SSH ramdisk
- `extract_data(udid: str, target_dir: Path, data_types: list[str]) -> dict` — pulls photos/contacts/messages via SSH

### Stub Mode
All functions check `platform.system()` and binary availability. On non-Linux or when binary not found, return `BypassResult(success=False, error="not_available", message="<tool> not found")`. Tests mock subprocess calls.

---

## Feature 2: FutureRestore (`futurerestore.py`)

Wraps `futurerestore` binary for iOS downgrade/upgrade when SHSH blobs + compatible SEP are available.

- `check_futurerestore_available() -> bool` — binary in PATH check
- `check_compatibility(device_model: str, target_version: str, blob_path: Path) -> RestoreCompatibility` — validates blob, checks SEP compatibility
- `run_futurerestore(udid: str, ipsw_path: Path, blob_path: Path, set_nonce: bool = True, progress_cb: Optional[Callable]) -> RestoreResult` — runs `futurerestore -t blob.shsh2 -l firmware.ipsw`, streams progress
- Integrates with existing firmware_manager for IPSW cache and SHSH blob directories
- Device must be in recovery/DFU mode (reuses existing helpers)

---

## Feature 3: Syslog Viewer (`syslog_service.py`)

Real-time iOS syslog streaming using pymobiledevice3's `OsTraceService`.

### Service Layer
- `start_syslog_stream(udid: str) -> AsyncGenerator[SyslogEntry, None]` — connects to device, yields parsed log entries (timestamp, process, pid, level, message)
- Server-side filtering via `SyslogFilter(process, level, keyword)`
- In-memory buffer of last 1000 entries for immediate display on connect

### WebSocket Endpoint
- `/ws/syslog/{udid}` — client connects, sends filter JSON, receives streaming log entries

### UI Panel
- Terminal-style dark panel in dashboard
- Process filter dropdown, level filter (Error/Warning/Info/Debug), text search
- Auto-scroll with pause button

---

## Feature 4: USB Cable Check

Added to `diagnostic_engine.py` (not a new service).

- `check_cable_quality(handle) -> CableCheckResult` — reads USB connection properties via pymobiledevice3 lockdown values
- Reports: connection type (USB 2.0/3.0), charging capability, data transfer speed
- Detects poor/fake cables via low negotiated speed or missing properties (not a full MFi check)

---

## Feature 5: Error Handling Hardening

Targeted improvements across existing code, not a new module.

- **Offline degradation**: `@with_fallback` decorator on SICKW API calls — returns cached results or "verification unavailable" when offline
- **Connection loss**: Device disconnect mid-operation returns partial results with `warnings` field
- **Startup resilience**: DB init, device polling, API startup wrapped with retry — one failure doesn't block the rest
- **Global exception handler**: FastAPI handler catches unhandled errors, logs them, returns structured JSON

---

## Feature 6: USB Build Script (`scripts/build_usb.sh`)

Bash script using `live-build` for reproducible Ubuntu 24.04 live USB creation.

- Uses debootstrap + live-build
- Pre-installs: Python 3.11, usbmuxd, libimobiledevice, idevicerestore, checkra1n, futurerestore
- Pre-configures: auto-start iDiag on login, udev rules for iPhone hotplug
- Copies iDiag app + pip dependencies into image
- Outputs `.iso` file for `dd` to USB
- Run: `sudo bash scripts/build_usb.sh` on any Debian/Ubuntu host

---

## Models (`app/models/tools.py`)

```python
class BypassResult(BaseModel):
    success: bool
    tool: Literal["checkra1n", "broque", "ssh_ramdisk"]
    error: Optional[str] = None
    message: Optional[str] = None
    timestamp: Optional[datetime] = None

class RestoreCompatibility(BaseModel):
    compatible: bool
    target_version: str
    blob_valid: bool
    sep_compatible: bool
    reason: Optional[str] = None

class SyslogEntry(BaseModel):
    timestamp: datetime
    process: str
    pid: int
    level: Literal["Emergency", "Alert", "Critical", "Error", "Warning", "Notice", "Info", "Debug"]
    message: str

class SyslogFilter(BaseModel):
    process: Optional[str] = None
    level: Optional[str] = None
    keyword: Optional[str] = None

class CableCheckResult(BaseModel):
    connection_type: str
    charge_capable: bool
    data_capable: bool
    negotiated_speed: Optional[str] = None
    warnings: list[str] = []
```

---

## API Endpoints (`app/api/tools.py`)

Router prefix: `/api/tools`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/tools/checkra1n/{udid}` | Run checkra1n jailbreak |
| POST | `/api/tools/broque/{udid}` | Run Broque Ramdisk bypass |
| POST | `/api/tools/ssh-ramdisk/{udid}` | Boot SSH ramdisk |
| POST | `/api/tools/ssh-ramdisk/{udid}/extract` | Extract data via SSH |
| POST | `/api/tools/futurerestore/{udid}` | Run FutureRestore downgrade |
| GET | `/api/tools/futurerestore/{udid}/check` | Check restore compatibility |
| GET | `/api/tools/cable/{udid}` | Check cable quality |
| GET | `/api/tools/availability` | Check which tools are installed |
| WS | `/ws/syslog/{udid}` | Syslog stream (on main WS router) |
