# iDiag Implementation Design

## Date: 2026-03-01
## Status: Approved

---

## Overview

iDiag is an all-in-one iPhone diagnostic, verification, and management tool for individual resellers. It replaces 3uTools + iTunes + IMEI checkers + spreadsheet tracking with a single portable application running from a bootable Linux USB drive.

This document captures the validated design decisions for implementation, derived from the PRD v2.0 and a collaborative design review.

---

## Key Design Decisions

### Platform & Environment
- **Target:** Linux bootable USB (Ubuntu 24.04 LTS)
- **Development:** Directly on the Linux USB from day one
- **Architecture:** Python 3.11+ / FastAPI / SQLite

### UI Approach: Hybrid Desktop Shell
- **pywebview** wraps the FastAPI web UI in a native desktop window
- Uses system WebKitGTK on Linux (no Chromium dependency)
- Frontend: server-rendered HTML + Tailwind CSS + HTMX (no JS build step)
- FastAPI serves API + static files on localhost
- Optional: expose port for phone access during deals

### External API Providers
| Check | Provider | API Type | Cost/device |
|---|---|---|---|
| FMI + Carrier + Blacklist (bundle) | SICKW.COM | REST JSON | $0.13 |
| Activation Lock (local) | pymobiledevice3 | USB/local | Free |
| Market pricing | Swappa scrape | HTTP GET | Free |
| **Total per device** | | | **$0.13** |

- SICKW.COM: Prepaid credits ($20 minimum), 4.9/5 Trustpilot, simple REST API
- Fallback: IMEICheck.com for granular checks at similar cost
- pymobiledevice3: `lockdown.get_value(key="ActivationState")` for local activation check

### Data Storage
- **SQLite** for inventory, diagnostics, sales (on persistent USB partition)
- **JSON files** for crash patterns, device capabilities, serial prefixes (version-controlled, shipped with app)
- No encryption at rest — physical USB security is user's responsibility

### Security
- FastAPI binds to 127.0.0.1 only
- No authentication layer for v1
- No encryption on SQLite database

### PDF Generation
- **WeasyPrint** (Python) — eliminates Node.js dependency entirely

---

## Project Structure

```
idiag/
├── app/
│   ├── main.py                  # FastAPI app + pywebview launcher
│   ├── config.py                # Settings, paths, constants
│   ├── models/                  # Pydantic models (shared data contracts)
│   │   ├── device.py
│   │   ├── diagnostic.py
│   │   ├── verification.py
│   │   ├── crash.py
│   │   ├── inventory.py
│   │   └── grading.py
│   ├── services/                # Business logic modules
│   │   ├── device_service.py    # Connection, auto-discovery, device info
│   │   ├── diagnostic_engine.py # Battery, parts, sensors, storage
│   │   ├── verification_service.py  # SICKW API, local activation check
│   │   ├── log_analyzer.py      # Crash report pull + pattern matching
│   │   ├── serial_decoder.py    # Serial/IMEI decode, fraud detection
│   │   ├── grading_engine.py    # Auto-grade calculation
│   │   ├── firmware_manager.py  # IPSW, SHSH, restore, DFU
│   │   ├── inventory_db.py      # SQLite CRUD
│   │   ├── report_generator.py  # PDF reports, erasure certs
│   │   └── bypass_tools.py      # checkra1n, Broque wrappers
│   ├── api/                     # FastAPI route handlers
│   │   ├── devices.py
│   │   ├── diagnostics.py
│   │   ├── verification.py
│   │   ├── inventory.py
│   │   ├── firmware.py
│   │   └── websocket.py         # Real-time device events
│   └── static/                  # Frontend (HTML + Tailwind + HTMX)
│       ├── index.html
│       ├── css/
│       └── js/
├── data/
│   ├── crash_patterns.json      # Crash signature database
│   ├── device_capabilities.json # Model -> capability map
│   └── serial_prefixes.json     # Serial decode lookup tables
├── db/                          # SQLite database (persistent partition)
├── tests/
├── scripts/
│   └── build_usb.sh             # USB image creation script
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Implementation Approach: MVP Sprint

Build the thinnest end-to-end slice first, then layer depth. Each sprint produces a usable tool.

### Sprint 1 (2 weeks): Core MVP
**Goal:** Plug in iPhone -> see diagnostics + verification -> grade -> save to inventory.

**Modules:**
1. Bootable USB image (Ubuntu 24.04 minimal, all deps pre-installed)
2. `device_service.py` — usbmuxd listener, auto-detect, `connect(udid)` -> DeviceHandle
3. `diagnostic_engine.py` — battery health/cycles/capacity, parts originality, storage
4. `serial_decoder.py` — decode serial -> factory/date/model/color/storage, IMEI validation
5. `verification_service.py` — SICKW.COM API (bundle check), local activation check
6. `log_analyzer.py` — pull crash reports, count by subsystem, 10 initial patterns
7. `grading_engine.py` — weighted auto-grade (battery 25%, parts 20%, crashes 20%, cosmetic 20%, locks 15%)
8. `inventory_db.py` — SQLite CRUD for devices + diagnostics
9. FastAPI + WebSocket — REST endpoints, WS for device events
10. pywebview dashboard — single-page pre-purchase summary, color-coded

**Data Flow (Pre-Purchase Check):**
```
USB Connect -> usbmuxd event -> device_service detects
  -> WebSocket "device_connected" -> Dashboard auto-triggers:
     ├─ device_service.get_info()     -> model, iOS, serial, IMEI
     ├─ diagnostic_engine.run()       -> battery, parts, storage
     ├─ serial_decoder.decode()       -> factory, date, fraud check
     ├─ verification_service.check()  -> SICKW API + local activation
     └─ log_analyzer.analyze()        -> crash pull + pattern match
  -> grading_engine.calculate()       -> weighted grade
  -> Dashboard: [GREEN/YELLOW/RED] [Grade: B+] [Value: $520]
```

**SQLite Schema (Sprint 1):**
```sql
CREATE TABLE devices (
    id INTEGER PRIMARY KEY,
    udid TEXT UNIQUE NOT NULL,
    serial TEXT,
    imei TEXT,
    model TEXT,
    ios_version TEXT,
    grade TEXT,
    status TEXT DEFAULT 'intake',
    buy_price REAL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE diagnostics (
    id INTEGER PRIMARY KEY,
    device_id INTEGER REFERENCES devices(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    battery_health REAL,
    battery_cycles INTEGER,
    parts_original BOOLEAN,
    storage_total REAL,
    storage_used REAL,
    raw_json TEXT
);

CREATE TABLE crash_reports (
    id INTEGER PRIMARY KEY,
    device_id INTEGER REFERENCES devices(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    process TEXT,
    exception TEXT,
    subsystem TEXT,
    severity INTEGER,
    count INTEGER DEFAULT 1
);

CREATE TABLE verifications (
    id INTEGER PRIMARY KEY,
    device_id INTEGER REFERENCES devices(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    blacklist_status TEXT,
    fmi_status TEXT,
    carrier TEXT,
    carrier_locked BOOLEAN,
    mdm TEXT,
    raw_json TEXT
);
```

### Sprint 2 (2 weeks): Deep Analysis & Intelligence
- Expand crash pattern DB to 30+ signatures
- Frequency trending + predictive failure flagging
- Identifier fraud detection (serial vs IMEI vs model cross-reference)
- Device capability routing (JSON capability map, UI filters by device)
- Market price lookup (Swappa scrape) + profit calculator
- Dashboard: crash detail view, device history

### Sprint 3 (2 weeks): Firmware & Recovery
- IPSW auto-download from Apple CDN, cache, SHA1 verify
- Signing status checker (Apple TSS query)
- SHSH blob saver (tsschecker integration)
- DFU/Recovery mode helpers (device-specific guided entry)
- Firmware restore (idevicerestore subprocess + WebSocket progress)
- Data wipe (EraseDevice) + erasure certificate

### Sprint 4 (2 weeks): Business Operations & Reports
- Photo station (webcam capture or file upload)
- PDF health report (WeasyPrint)
- Listing template generator (eBay/Swappa/Facebook)
- Sales tracking (buy/sell/profit/fees/days-in-inventory)
- QR code labels (link to device diagnostic page)
- Bulk CSV/JSON export

### Sprint 5 (2 weeks): Edge Cases & Hardening
- Broque Ramdisk (A9-A11 iCloud bypass)
- checkra1n (jailbreak for advanced recovery)
- SSH Ramdisk (data extraction from locked devices)
- FutureRestore (downgrade when blobs + SEP available)
- USB cable authenticity check
- Syslog viewer (real-time stream)
- Error handling hardening + offline degradation
- Reproducible USB image build script

---

## Module Communication

All inter-module communication flows through the FastAPI layer. No direct cross-module imports except shared Pydantic models in `app/models/`.

Data flow between modules:
- `device_service` -> provides DeviceHandle to all other services
- `diagnostic_engine`, `log_analyzer`, `verification_service`, `serial_decoder` -> produce independent results
- `grading_engine` -> consumes results from all above via API/DB, not direct import
- `inventory_db` -> stores everything, read by `report_generator` and `grading_engine`

---

## Crash Pattern Database (Initial 10 Signatures)

Stored as `data/crash_patterns.json`:

```json
[
  {"pattern": "kernel panic in AppleH.*CamISP", "subsystem": "Camera", "severity": 5, "description": "Camera hardware failure - likely needs replacement"},
  {"pattern": "kernel panic in AppleBCMWLAN", "subsystem": "WiFi", "severity": 4, "description": "WiFi chipset instability - may need board repair"},
  {"pattern": "EXC_RESOURCE.*cpu.*backboardd", "subsystem": "Display", "severity": 3, "description": "Display driver stress - possible screen issue"},
  {"pattern": "kernel panic in AppleARMPMU", "subsystem": "Battery/Power", "severity": 5, "description": "Power management failure - battery or board issue"},
  {"pattern": "watchdog timeout in CommCenter", "subsystem": "Baseband", "severity": 4, "description": "Cellular modem hang - possible baseband failure"},
  {"pattern": "kernel panic in AppleSEP", "subsystem": "Security", "severity": 5, "description": "Secure Enclave issue - Face ID/Touch ID may fail"},
  {"pattern": "EXC_BAD_ACCESS in AGXMetal", "subsystem": "GPU", "severity": 3, "description": "GPU crash - monitor frequency, may indicate board issue"},
  {"pattern": "kernel panic in IONVMe", "subsystem": "Storage", "severity": 5, "description": "NAND storage controller panic - high brick risk"},
  {"pattern": "repeated springboardd crashes", "subsystem": "System", "severity": 2, "description": "SpringBoard instability - usually software, try restore"},
  {"pattern": "thermalmonitord EXC_RESOURCE", "subsystem": "Thermal", "severity": 4, "description": "Thermal throttling failure - possible thermal paste issue"}
]
```

---

## Grading Algorithm

| Component | Weight | Data Source | A | B | C | D |
|---|---|---|---|---|---|---|
| Battery Health | 25% | DiagnosticsService | 100-90% | 89-80% | 79-70% | <70% |
| Parts Originality | 20% | MobileGestalt | All original | 1 replaced | 2+ replaced | Critical replaced |
| Crash History | 20% | log_analyzer | 0-2 minor | 3-10 | 11-30 or 1 critical | 30+ or hardware |
| Cosmetic Condition | 20% | Manual input | No damage | Light scratches | Cracks/dents | Major damage |
| Lock/Activation | 15% | verification_service | Clean | Carrier locked | MDM | iCloud locked |

Grade mapping: A=4, B=3, C=2, D=1. Weighted average -> final letter grade.
Note: Cosmetic requires manual input — auto-grade is partial until cosmetic is entered.

---

## Dependencies (Pre-installed on USB)

| Package | Install | Purpose |
|---|---|---|
| usbmuxd | apt | Apple USB multiplexing daemon |
| libimobiledevice-utils | apt | CLI fallback tools |
| idevicerestore | apt | Firmware restore |
| Python 3.11+ | apt | Runtime |
| pymobiledevice3 | pip | Primary device API |
| FastAPI + Uvicorn | pip | Web server |
| pywebview | pip | Desktop window shell |
| WeasyPrint | pip | PDF generation |
| httpx | pip | Async HTTP (SICKW API) |
| SQLite 3 | built-in | Database |
| Tailwind CSS | CDN/local | Styling |
| HTMX | CDN/local | Dynamic updates |
| checkra1n | binary | Jailbreak (Sprint 5) |
| Broque Ramdisk | git clone | iCloud bypass (Sprint 5) |
| tsschecker | binary | SHSH blob saving (Sprint 3) |
| futurerestore | binary | iOS downgrade (Sprint 5) |
