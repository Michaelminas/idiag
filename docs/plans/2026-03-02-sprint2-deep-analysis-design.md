# Sprint 2: Deep Analysis & Intelligence — Design

## Overview

Sprint 2 builds on Sprint 1's core device connection, diagnostics, and inventory foundation to add intelligent crash analysis, enhanced fraud detection, a unified snapshot API, manual pricing, and a richer dashboard.

## Slice 1: Crash Intelligence

### 1a. Expand Crash Patterns (10 → 30+)

Add 20+ new patterns to `data/crash_patterns.json` covering:

| Subsystem | Pattern regex | Severity |
|-----------|--------------|----------|
| Audio | `kernel panic in AppleAudioCodecs` | 4 |
| Bluetooth | `kernel panic in AppleBCMBTFW` | 3 |
| NFC | `kernel panic in AppleNFC` | 3 |
| Accelerometer | `EXC_BAD_ACCESS in CoreMotion` | 3 |
| Gyroscope | `kernel panic in AppleARMGyro` | 3 |
| Face ID | `kernel panic in BiometricKit\|pearl` | 5 |
| Touch ID | `kernel panic in AppleMesa` | 5 |
| Proximity | `EXC_BAD_ACCESS in AppleProximity` | 2 |
| LiDAR | `kernel panic in AppleLiDAR` | 3 |
| Taptic | `kernel panic in AppleHaptics` | 3 |
| Charging | `kernel panic in AppleUSBPD` | 4 |
| USB | `kernel panic in IOUSBDeviceFamily` | 3 |
| Compass | `EXC_BAD_ACCESS in AppleARMCompass` | 2 |
| Ambient Light | `kernel panic in AppleALS` | 2 |
| Barometer | `EXC_BAD_ACCESS in AppleBarometer` | 2 |
| UWB | `kernel panic in AppleUWB` | 3 |
| Neural Engine | `kernel panic in ANE` | 4 |
| Memory | `EXC_RESOURCE.*jetsam` | 3 |
| Sleep/Wake | `kernel panic in SleepServices` | 4 |
| SIM | `watchdog timeout in coreTelephony` | 3 |
| Recovery Loop | `repeated iBoot.*restore` | 5 |

### 1b. Frequency Trending

New function `get_crash_trend(udid)` in `log_analyzer.py`:
- Queries `crash_reports` table for all historical scans of the device
- Compares current subsystem counts vs. most recent previous scan
- Returns per-subsystem trend: `improving` / `stable` / `worsening`

New model field on `CrashAnalysis`:
```python
trends: dict[str, str] = {}  # subsystem -> "improving"|"stable"|"worsening"
```

### 1c. Predictive Failure Flagging

If a subsystem is `worsening` AND severity >= 4, flag as predicted imminent failure.

New model field on `CrashAnalysis`:
```python
predicted_failures: list[str] = []  # plain-English failure predictions
```

Summary example: "Camera hardware — 47 crashes in 30 days, increasing trend. Recommend pricing for camera replacement."

## Slice 2: Enhanced Fraud Detection

### 2a. TAC-Based IMEI→Model Validation

Add `TAC_MAP: dict[str, str]` to `serial_decoder.py` mapping 8-digit TAC codes to device model names.

In `cross_reference_check()`, compare TAC-derived model against ProductType-derived model and serial model code. Flag mismatches.

### 2b. Randomized Serial Detection

Already handled for non-12-char serials. Enhance by adding a `randomized_note` field to `FraudCheck`:
- "This device has a randomized serial (post-2021). Serial-based decoding unavailable."

### 2c. Fraud Scoring

Add `fraud_score: int` (0-100) to `FraudCheck`:
- IMEI invalid: +40
- Model mismatch (A-number vs ProductType): +30
- TAC mismatch: +20
- Unknown identifiers: +10

## Slice 3: Unified Snapshot API + Pricing

### 3a. Snapshot Endpoint

`GET /api/devices/{udid}/snapshot` assembles a full `DeviceSnapshot`:
1. `device_service.get_device_info(udid)` → `DeviceInfo`
2. `diagnostic_engine.run_diagnostics(udid)` → `DiagnosticResult`
3. `log_analyzer.analyze_device(udid)` → `CrashAnalysis`
4. `verification_service.check_device(imei, udid)` → `VerificationResult`
5. `grading_engine.calculate_grade(...)` → `DeviceGrade`
6. `inventory_db.get_device_by_udid(udid)` → `DeviceRecord`

Returns assembled `DeviceSnapshot`. Saves results to DB for history.

### 3b. Pricing Fields

Add to `DeviceRecord`:
- `sell_price: Optional[float]`
- `profit: Optional[float]` (computed: sell_price - buy_price)

Exposed via existing `POST /api/inventory/devices`.

### 3c. History Endpoints

- `GET /api/inventory/devices/{id}/diagnostics` — historical diagnostic records
- `GET /api/inventory/devices/{id}/verifications` — historical verification records

## Slice 4: Dashboard v2

### 4a. Snapshot-Driven View
On WebSocket `device_connected`, auto-fetch snapshot endpoint and render all panels.

### 4b. Crash Detail Panel
- Expandable crash match list with severity badges (red/orange/yellow/blue/grey)
- Trend indicators (arrows) per subsystem
- Predicted failure warnings in red

### 4c. Device History Tab
- Timeline of past diagnostic scans and verifications
- Grade change history

### 4d. Pricing Fields
- Buy price / sell price inputs on device card
- Auto-calculated profit (green=positive, red=negative)

### 4e. Device Capability Display
- Show capability chips from `device_capabilities.json`
- New `GET /api/devices/{udid}/capabilities` endpoint

## Slice 5: Test Infrastructure

### 5a. Shared Fixtures (`tests/conftest.py`)
- Mock `pymobiledevice3.lockdown.create_using_usbmux`
- Mock `CrashReportsManager` with sample crash files
- Mock HTTP for SICKW API
- Add `pytest-mock` dependency

### 5b. New Test Files
- `tests/test_diagnostic_engine.py` — battery/parts/storage with mocked device
- `tests/test_log_analyzer.py` — pattern matching, trending, predictive flagging
- `tests/test_verification_service.py` — SICKW API mock, local checks
- `tests/test_snapshot_api.py` — FastAPI TestClient integration tests
- `tests/test_fraud_detection.py` — TAC validation, fraud scoring, randomized serials

### 5c. Test Fixtures
- `tests/fixtures/sample_camera_crash.ips`
- `tests/fixtures/sample_battery_crash.ips`
- Additional fixtures for new pattern coverage

## Files Modified

| File | Change |
|------|--------|
| `data/crash_patterns.json` | Expand from 10 to 30+ patterns |
| `app/models/crash.py` | Add `trends`, `predicted_failures` fields |
| `app/models/device.py` | Add `sell_price`, `profit` to DeviceRecord |
| `app/models/inventory.py` | Add `fraud_score`, `randomized_note` to FraudCheck |
| `app/services/log_analyzer.py` | Add `get_crash_trend()`, predictive flagging |
| `app/services/serial_decoder.py` | Add TAC_MAP, enhanced cross_reference_check, fraud scoring |
| `app/services/inventory_db.py` | Add history query methods, schema migration for new columns |
| `app/api/diagnostics.py` | Add snapshot endpoint |
| `app/api/inventory.py` | Add history endpoints |
| `app/api/devices.py` | Add capabilities endpoint (new file) |
| `app/static/index.html` | Dashboard v2 overhaul |
| `tests/conftest.py` | New: shared fixtures and mocks |
| `tests/test_diagnostic_engine.py` | New |
| `tests/test_log_analyzer.py` | New |
| `tests/test_verification_service.py` | New |
| `tests/test_snapshot_api.py` | New |
| `tests/test_fraud_detection.py` | New |
| `tests/fixtures/*.ips` | New: sample crash report files |
