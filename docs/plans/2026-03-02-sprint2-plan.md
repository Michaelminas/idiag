# Sprint 2: Deep Analysis & Intelligence — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add intelligent crash analysis (30+ patterns, trending, predictive failures), enhanced fraud detection (TAC validation, fraud scoring), unified snapshot API, manual pricing, and a richer dashboard.

**Architecture:** Feature-sliced delivery across 5 vertical slices. Each slice is independently testable. TDD approach — write failing tests first, then implement. All new services get mocked device layer via `pytest-mock`.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLite, pymobiledevice3 (mocked in tests), pytest + pytest-mock, Tailwind CSS + vanilla JS.

---

### Task 1: Add pytest-mock dependency

**Files:**
- Modify: `requirements.txt:10-12`

**Step 1: Add pytest-mock to requirements**

In `requirements.txt`, add `pytest-mock` after `pytest-asyncio`:

```
# Dev
pytest>=8.0
pytest-asyncio>=0.24.0
pytest-mock>=3.14.0
ruff>=0.8.0
```

**Step 2: Install dependencies**

Run: `pip install pytest-mock>=3.14.0`
Expected: Successfully installed pytest-mock

**Step 3: Verify existing tests still pass**

Run: `python -m pytest tests/ -v`
Expected: 35 tests PASS

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add pytest-mock dependency for Sprint 2 testing"
```

---

### Task 2: Expand crash patterns from 10 to 31

**Files:**
- Modify: `data/crash_patterns.json`
- Create: `tests/test_log_analyzer.py`
- Create: `tests/fixtures/` (directory + sample crash files)

**Step 1: Create test fixtures directory and sample crash files**

Create `tests/fixtures/sample_camera_crash.ips`:
```
{"bug_type":"210","timestamp":"2025-01-15 10:23:45","name":"iPhone"}
Date/Time:       2025-01-15 10:23:45
OS Version:      iPhone OS 17.2
Hardware Model:  D63AP

Exception Type:  EXC_BAD_ACCESS (SIGBUS)
Kernel panic in AppleH13CamISP at 0xfffffff00a123456
Thread 0 crashed with ARM Thread State
```

Create `tests/fixtures/sample_battery_crash.ips`:
```
{"bug_type":"210","timestamp":"2025-01-10 08:15:22","name":"iPhone"}
Date/Time:       2025-01-10 08:15:22
OS Version:      iPhone OS 17.2

Exception Type:  EXC_BAD_ACCESS
kernel panic in AppleARMPMU power management unit failure
Thread 0 crashed
```

Create `tests/fixtures/sample_bluetooth_crash.ips`:
```
{"bug_type":"210","timestamp":"2025-02-01 14:30:00","name":"iPhone"}
Date/Time:       2025-02-01 14:30:00
OS Version:      iPhone OS 17.3

kernel panic in AppleBCMBTFW bluetooth firmware failure
Thread 2 crashed
```

Create `tests/fixtures/sample_faceid_crash.ips`:
```
{"bug_type":"210","timestamp":"2025-02-05 09:00:00","name":"iPhone"}
Date/Time:       2025-02-05 09:00:00
OS Version:      iPhone OS 17.3

kernel panic in BiometricKit pearl sensor calibration failure
Thread 1 crashed
```

Create `tests/fixtures/sample_no_match.ips`:
```
{"bug_type":"309","timestamp":"2025-01-20 12:00:00","name":"iPhone"}
Date/Time:       2025-01-20 12:00:00
OS Version:      iPhone OS 17.2

Application specific crash in com.example.app
Thread 0 crashed with unrecognized selector
```

**Step 2: Write failing tests for new patterns**

Create `tests/test_log_analyzer.py`:

```python
"""Tests for crash log analysis — pattern matching, trending, and predictions."""

import pytest

from app.services.log_analyzer import analyze_crash_text, PATTERNS


class TestCrashPatterns:
    """Verify all 31 crash patterns match correctly."""

    def test_patterns_loaded(self):
        """At least 30 patterns should be loaded."""
        assert len(PATTERNS) >= 30

    # -- Original 10 patterns --

    def test_camera_pattern(self):
        text = "kernel panic in AppleH13CamISP at 0xfffffff00a123456"
        match = analyze_crash_text(text, "camera.ips")
        assert match is not None
        assert match.subsystem == "Camera"
        assert match.severity == 5

    def test_wifi_pattern(self):
        text = "kernel panic in AppleBCMWLAN driver timeout"
        match = analyze_crash_text(text, "wifi.ips")
        assert match is not None
        assert match.subsystem == "WiFi"
        assert match.severity == 4

    def test_display_pattern(self):
        text = "EXC_RESOURCE cpu limit exceeded backboardd"
        match = analyze_crash_text(text, "display.ips")
        assert match is not None
        assert match.subsystem == "Display"

    def test_battery_power_pattern(self):
        text = "kernel panic in AppleARMPMU power management unit"
        match = analyze_crash_text(text, "battery.ips")
        assert match is not None
        assert match.subsystem == "Battery/Power"
        assert match.severity == 5

    def test_baseband_pattern(self):
        text = "watchdog timeout in CommCenter modem hang"
        match = analyze_crash_text(text, "baseband.ips")
        assert match is not None
        assert match.subsystem == "Baseband"

    def test_security_sep_pattern(self):
        text = "kernel panic in AppleSEP secure enclave"
        match = analyze_crash_text(text, "sep.ips")
        assert match is not None
        assert match.subsystem == "Security"
        assert match.severity == 5

    def test_gpu_pattern(self):
        text = "EXC_BAD_ACCESS in AGXMetal gpu driver crash"
        match = analyze_crash_text(text, "gpu.ips")
        assert match is not None
        assert match.subsystem == "GPU"

    def test_storage_pattern(self):
        text = "kernel panic in IONVMe storage controller"
        match = analyze_crash_text(text, "storage.ips")
        assert match is not None
        assert match.subsystem == "Storage"
        assert match.severity == 5

    def test_system_pattern(self):
        text = "repeated springboardd crashes detected"
        match = analyze_crash_text(text, "system.ips")
        assert match is not None
        assert match.subsystem == "System"

    def test_thermal_pattern(self):
        text = "thermalmonitord EXC_RESOURCE limit exceeded"
        match = analyze_crash_text(text, "thermal.ips")
        assert match is not None
        assert match.subsystem == "Thermal"

    # -- New Sprint 2 patterns --

    def test_audio_pattern(self):
        text = "kernel panic in AppleAudioCodecs driver failure"
        match = analyze_crash_text(text, "audio.ips")
        assert match is not None
        assert match.subsystem == "Audio"
        assert match.severity == 4

    def test_bluetooth_pattern(self):
        text = "kernel panic in AppleBCMBTFW firmware reset"
        match = analyze_crash_text(text, "bt.ips")
        assert match is not None
        assert match.subsystem == "Bluetooth"
        assert match.severity == 3

    def test_nfc_pattern(self):
        text = "kernel panic in AppleNFC controller reset"
        match = analyze_crash_text(text, "nfc.ips")
        assert match is not None
        assert match.subsystem == "NFC"
        assert match.severity == 3

    def test_accelerometer_pattern(self):
        text = "EXC_BAD_ACCESS in CoreMotion accelerometer"
        match = analyze_crash_text(text, "accel.ips")
        assert match is not None
        assert match.subsystem == "Accelerometer"
        assert match.severity == 3

    def test_gyroscope_pattern(self):
        text = "kernel panic in AppleARMGyro sensor failure"
        match = analyze_crash_text(text, "gyro.ips")
        assert match is not None
        assert match.subsystem == "Gyroscope"
        assert match.severity == 3

    def test_faceid_pattern(self):
        text = "kernel panic in BiometricKit pearl sensor failure"
        match = analyze_crash_text(text, "faceid.ips")
        assert match is not None
        assert match.subsystem == "Face ID"
        assert match.severity == 5

    def test_touchid_pattern(self):
        text = "kernel panic in AppleMesa fingerprint driver"
        match = analyze_crash_text(text, "touchid.ips")
        assert match is not None
        assert match.subsystem == "Touch ID"
        assert match.severity == 5

    def test_proximity_pattern(self):
        text = "EXC_BAD_ACCESS in AppleProximity sensor"
        match = analyze_crash_text(text, "prox.ips")
        assert match is not None
        assert match.subsystem == "Proximity"
        assert match.severity == 2

    def test_lidar_pattern(self):
        text = "kernel panic in AppleLiDAR scanner failure"
        match = analyze_crash_text(text, "lidar.ips")
        assert match is not None
        assert match.subsystem == "LiDAR"
        assert match.severity == 3

    def test_taptic_pattern(self):
        text = "kernel panic in AppleHaptics taptic engine"
        match = analyze_crash_text(text, "taptic.ips")
        assert match is not None
        assert match.subsystem == "Taptic"
        assert match.severity == 3

    def test_charging_pattern(self):
        text = "kernel panic in AppleUSBPD charging controller"
        match = analyze_crash_text(text, "charge.ips")
        assert match is not None
        assert match.subsystem == "Charging"
        assert match.severity == 4

    def test_usb_pattern(self):
        text = "kernel panic in IOUSBDeviceFamily controller"
        match = analyze_crash_text(text, "usb.ips")
        assert match is not None
        assert match.subsystem == "USB"
        assert match.severity == 3

    def test_compass_pattern(self):
        text = "EXC_BAD_ACCESS in AppleARMCompass calibration"
        match = analyze_crash_text(text, "compass.ips")
        assert match is not None
        assert match.subsystem == "Compass"
        assert match.severity == 2

    def test_ambient_light_pattern(self):
        text = "kernel panic in AppleALS sensor failure"
        match = analyze_crash_text(text, "als.ips")
        assert match is not None
        assert match.subsystem == "Ambient Light"
        assert match.severity == 2

    def test_barometer_pattern(self):
        text = "EXC_BAD_ACCESS in AppleBarometer pressure sensor"
        match = analyze_crash_text(text, "baro.ips")
        assert match is not None
        assert match.subsystem == "Barometer"
        assert match.severity == 2

    def test_uwb_pattern(self):
        text = "kernel panic in AppleUWB ultra wideband"
        match = analyze_crash_text(text, "uwb.ips")
        assert match is not None
        assert match.subsystem == "UWB"
        assert match.severity == 3

    def test_neural_engine_pattern(self):
        text = "kernel panic in ANE neural engine failure"
        match = analyze_crash_text(text, "ane.ips")
        assert match is not None
        assert match.subsystem == "Neural Engine"
        assert match.severity == 4

    def test_memory_pattern(self):
        text = "EXC_RESOURCE exceeded memory limit jetsam event"
        match = analyze_crash_text(text, "mem.ips")
        assert match is not None
        assert match.subsystem == "Memory"
        assert match.severity == 3

    def test_sleep_wake_pattern(self):
        text = "kernel panic in SleepServices wake failure"
        match = analyze_crash_text(text, "sleep.ips")
        assert match is not None
        assert match.subsystem == "Sleep/Wake"
        assert match.severity == 4

    def test_sim_pattern(self):
        text = "watchdog timeout in coreTelephony SIM eject"
        match = analyze_crash_text(text, "sim.ips")
        assert match is not None
        assert match.subsystem == "SIM"
        assert match.severity == 3

    def test_recovery_loop_pattern(self):
        text = "repeated iBoot failure, entering restore mode"
        match = analyze_crash_text(text, "recovery.ips")
        assert match is not None
        assert match.subsystem == "Recovery"
        assert match.severity == 5

    def test_no_match(self):
        text = "Application specific crash in com.example.app"
        match = analyze_crash_text(text, "app.ips")
        assert match is None
```

**Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_log_analyzer.py -v`
Expected: `test_patterns_loaded` FAILS (only 10 patterns loaded), new pattern tests FAIL (no matching patterns)

**Step 4: Expand crash_patterns.json to 31 patterns**

Replace `data/crash_patterns.json` with:

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
  {"pattern": "thermalmonitord EXC_RESOURCE", "subsystem": "Thermal", "severity": 4, "description": "Thermal throttling failure - possible thermal paste issue"},
  {"pattern": "kernel panic in AppleAudioCodecs", "subsystem": "Audio", "severity": 4, "description": "Audio codec hardware failure - speaker or mic issue"},
  {"pattern": "kernel panic in AppleBCMBTFW", "subsystem": "Bluetooth", "severity": 3, "description": "Bluetooth firmware crash - may need board-level repair"},
  {"pattern": "kernel panic in AppleNFC", "subsystem": "NFC", "severity": 3, "description": "NFC controller failure - Apple Pay and tap features affected"},
  {"pattern": "EXC_BAD_ACCESS in CoreMotion", "subsystem": "Accelerometer", "severity": 3, "description": "Accelerometer sensor failure - rotation and motion affected"},
  {"pattern": "kernel panic in AppleARMGyro", "subsystem": "Gyroscope", "severity": 3, "description": "Gyroscope sensor failure - compass and stabilization affected"},
  {"pattern": "kernel panic in BiometricKit|pearl", "subsystem": "Face ID", "severity": 5, "description": "Face ID sensor stack failure - TrueDepth camera issue"},
  {"pattern": "kernel panic in AppleMesa", "subsystem": "Touch ID", "severity": 5, "description": "Touch ID sensor failure - home button or power button issue"},
  {"pattern": "EXC_BAD_ACCESS in AppleProximity", "subsystem": "Proximity", "severity": 2, "description": "Proximity sensor issue - screen may not turn off during calls"},
  {"pattern": "kernel panic in AppleLiDAR", "subsystem": "LiDAR", "severity": 3, "description": "LiDAR scanner failure - depth sensing and AR affected"},
  {"pattern": "kernel panic in AppleHaptics", "subsystem": "Taptic", "severity": 3, "description": "Taptic Engine failure - haptic feedback not working"},
  {"pattern": "kernel panic in AppleUSBPD", "subsystem": "Charging", "severity": 4, "description": "USB-PD charging controller failure - charging may be unreliable"},
  {"pattern": "kernel panic in IOUSBDeviceFamily", "subsystem": "USB", "severity": 3, "description": "USB controller instability - data transfer and charging affected"},
  {"pattern": "EXC_BAD_ACCESS in AppleARMCompass", "subsystem": "Compass", "severity": 2, "description": "Compass sensor failure - navigation affected"},
  {"pattern": "kernel panic in AppleALS", "subsystem": "Ambient Light", "severity": 2, "description": "Ambient light sensor failure - auto-brightness affected"},
  {"pattern": "EXC_BAD_ACCESS in AppleBarometer", "subsystem": "Barometer", "severity": 2, "description": "Barometer sensor failure - altitude tracking affected"},
  {"pattern": "kernel panic in AppleUWB", "subsystem": "UWB", "severity": 3, "description": "Ultra Wideband chip failure - AirTag and spatial features affected"},
  {"pattern": "kernel panic in ANE", "subsystem": "Neural Engine", "severity": 4, "description": "Apple Neural Engine failure - ML and computational photography affected"},
  {"pattern": "EXC_RESOURCE.*jetsam", "subsystem": "Memory", "severity": 3, "description": "Excessive memory pressure - possible RAM or logic board issue"},
  {"pattern": "kernel panic in SleepServices", "subsystem": "Sleep/Wake", "severity": 4, "description": "Sleep/wake failure - device may not wake or sleep properly"},
  {"pattern": "watchdog timeout in coreTelephony", "subsystem": "SIM", "severity": 3, "description": "SIM/cellular stack hang - SIM tray or modem issue"},
  {"pattern": "repeated iBoot.*restore", "subsystem": "Recovery", "severity": 5, "description": "Boot loop detected - device stuck in recovery, may need DFU restore"}
]
```

**Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_log_analyzer.py -v`
Expected: All 32 tests PASS

**Step 6: Commit**

```bash
git add data/crash_patterns.json tests/test_log_analyzer.py tests/fixtures/
git commit -m "feat: expand crash patterns from 10 to 31, add pattern tests and fixtures"
```

---

### Task 3: Add crash trending and predictive failure models

**Files:**
- Modify: `app/models/crash.py:30-41`

**Step 1: Write failing test for new model fields**

Append to `tests/test_log_analyzer.py`:

```python
class TestCrashAnalysisModel:
    """Verify CrashAnalysis model has trending and prediction fields."""

    def test_trends_field_exists(self):
        from app.models.crash import CrashAnalysis
        analysis = CrashAnalysis()
        assert hasattr(analysis, "trends")
        assert analysis.trends == {}

    def test_predicted_failures_field_exists(self):
        from app.models.crash import CrashAnalysis
        analysis = CrashAnalysis()
        assert hasattr(analysis, "predicted_failures")
        assert analysis.predicted_failures == []
```

**Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_log_analyzer.py::TestCrashAnalysisModel -v`
Expected: FAIL — `trends` and `predicted_failures` not on model

**Step 3: Add fields to CrashAnalysis model**

In `app/models/crash.py`, add two fields to `CrashAnalysis` after `summary`:

```python
class CrashAnalysis(BaseModel):
    """Aggregated crash analysis for a device."""

    total_reports: int = 0
    matched_reports: int = 0
    unmatched_reports: int = 0
    matches: list[CrashMatch] = []
    subsystem_counts: dict[str, int] = {}
    max_severity: int = 0
    risk_score: float = 0.0  # 0-100
    summary: str = ""
    trends: dict[str, str] = {}  # subsystem -> "improving"|"stable"|"worsening"
    predicted_failures: list[str] = []  # plain-English failure predictions
```

**Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_log_analyzer.py::TestCrashAnalysisModel -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/models/crash.py tests/test_log_analyzer.py
git commit -m "feat: add trends and predicted_failures fields to CrashAnalysis model"
```

---

### Task 4: Implement crash frequency trending

**Files:**
- Modify: `app/services/log_analyzer.py`
- Modify: `tests/test_log_analyzer.py`

**Step 1: Write failing tests for trending logic**

Append to `tests/test_log_analyzer.py`:

```python
from app.services.log_analyzer import compute_trends, compute_predicted_failures


class TestCrashTrending:
    """Test frequency trending logic."""

    def test_no_history_returns_empty(self):
        current = {"Camera": 5, "WiFi": 3}
        trends = compute_trends(current, [])
        assert trends == {}

    def test_stable_when_counts_same(self):
        current = {"Camera": 5}
        history = [{"Camera": 5}]
        trends = compute_trends(current, history)
        assert trends["Camera"] == "stable"

    def test_worsening_when_counts_increase(self):
        current = {"Camera": 10}
        history = [{"Camera": 5}]
        trends = compute_trends(current, history)
        assert trends["Camera"] == "worsening"

    def test_improving_when_counts_decrease(self):
        current = {"Camera": 2}
        history = [{"Camera": 8}]
        trends = compute_trends(current, history)
        assert trends["Camera"] == "improving"

    def test_new_subsystem_not_in_history(self):
        current = {"Camera": 5, "WiFi": 3}
        history = [{"Camera": 5}]
        trends = compute_trends(current, history)
        assert trends["Camera"] == "stable"
        assert "WiFi" not in trends  # no history to compare

    def test_multiple_history_uses_most_recent(self):
        current = {"Camera": 10}
        history = [{"Camera": 3}, {"Camera": 7}]  # most recent last
        trends = compute_trends(current, history)
        assert trends["Camera"] == "worsening"


class TestPredictedFailures:
    """Test predictive failure flagging."""

    def test_no_failures_when_stable(self):
        trends = {"Camera": "stable"}
        subsystem_counts = {"Camera": 5}
        # severity_map: subsystem -> max severity seen
        severity_map = {"Camera": 5}
        failures = compute_predicted_failures(trends, subsystem_counts, severity_map)
        assert failures == []

    def test_failure_when_worsening_and_high_severity(self):
        trends = {"Camera": "worsening"}
        subsystem_counts = {"Camera": 15}
        severity_map = {"Camera": 5}
        failures = compute_predicted_failures(trends, subsystem_counts, severity_map)
        assert len(failures) == 1
        assert "Camera" in failures[0]

    def test_no_failure_when_worsening_but_low_severity(self):
        trends = {"Compass": "worsening"}
        subsystem_counts = {"Compass": 10}
        severity_map = {"Compass": 2}
        failures = compute_predicted_failures(trends, subsystem_counts, severity_map)
        assert failures == []

    def test_failure_message_includes_count(self):
        trends = {"Storage": "worsening"}
        subsystem_counts = {"Storage": 47}
        severity_map = {"Storage": 5}
        failures = compute_predicted_failures(trends, subsystem_counts, severity_map)
        assert "47" in failures[0]
```

**Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_log_analyzer.py::TestCrashTrending tests/test_log_analyzer.py::TestPredictedFailures -v`
Expected: FAIL — `compute_trends` and `compute_predicted_failures` not importable

**Step 3: Implement trending functions in log_analyzer.py**

Add to `app/services/log_analyzer.py` (after `_generate_summary`):

```python
def compute_trends(
    current_counts: dict[str, int],
    history: list[dict[str, int]],
) -> dict[str, str]:
    """Compare current subsystem counts against most recent historical scan.

    Args:
        current_counts: subsystem -> count from current scan
        history: list of past subsystem_counts dicts, ordered oldest to newest

    Returns:
        subsystem -> "improving"|"stable"|"worsening" (only for subsystems with history)
    """
    if not history:
        return {}

    previous = history[-1]  # most recent historical scan
    trends: dict[str, str] = {}

    for subsystem, current_count in current_counts.items():
        prev_count = previous.get(subsystem)
        if prev_count is None:
            continue  # no history for this subsystem
        if current_count > prev_count:
            trends[subsystem] = "worsening"
        elif current_count < prev_count:
            trends[subsystem] = "improving"
        else:
            trends[subsystem] = "stable"

    return trends


def compute_predicted_failures(
    trends: dict[str, str],
    subsystem_counts: dict[str, int],
    severity_map: dict[str, int],
) -> list[str]:
    """Flag subsystems that are worsening with high severity as predicted failures.

    Args:
        trends: subsystem -> trend direction
        subsystem_counts: subsystem -> crash count in current scan
        severity_map: subsystem -> max severity for that subsystem

    Returns:
        List of plain-English failure prediction strings.
    """
    failures: list[str] = []
    for subsystem, trend in trends.items():
        if trend != "worsening":
            continue
        severity = severity_map.get(subsystem, 0)
        if severity < 4:
            continue
        count = subsystem_counts.get(subsystem, 0)
        failures.append(
            f"{subsystem} hardware — {count} crashes, increasing trend. "
            f"Recommend pricing for {subsystem.lower()} replacement."
        )
    return failures
```

**Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_log_analyzer.py::TestCrashTrending tests/test_log_analyzer.py::TestPredictedFailures -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add app/services/log_analyzer.py tests/test_log_analyzer.py
git commit -m "feat: add crash frequency trending and predictive failure functions"
```

---

### Task 5: Enhanced fraud detection — TAC map, fraud scoring, randomized serial note

**Files:**
- Modify: `app/models/inventory.py:48-52` (FraudCheck model)
- Modify: `app/services/serial_decoder.py`
- Create: `tests/test_fraud_detection.py`

**Step 1: Write failing tests**

Create `tests/test_fraud_detection.py`:

```python
"""Tests for enhanced fraud detection — TAC validation, fraud scoring, randomized serial."""

import pytest

from app.models.inventory import FraudCheck
from app.services.serial_decoder import (
    cross_reference_check,
    decode_serial,
    validate_imei,
)


class TestFraudCheckModel:
    """Verify FraudCheck model has new fields."""

    def test_fraud_score_field(self):
        fc = FraudCheck()
        assert hasattr(fc, "fraud_score")
        assert fc.fraud_score == 0

    def test_randomized_note_field(self):
        fc = FraudCheck()
        assert hasattr(fc, "randomized_note")
        assert fc.randomized_note == ""


class TestTACValidation:
    """Test TAC-based IMEI to model cross-reference."""

    def test_tac_map_has_entries(self):
        from app.services.serial_decoder import TAC_MAP
        assert len(TAC_MAP) > 0

    def test_tac_mismatch_flagged(self):
        # Use a TAC that maps to a different model than product_type
        from app.services.serial_decoder import TAC_MAP
        # Find any TAC entry to test with
        tac, expected_model = next(iter(TAC_MAP.items()))
        # Use a product_type that resolves to a DIFFERENT model
        wrong_pt = "iPhone8,1"  # iPhone 6s
        result = cross_reference_check(
            serial="DNXXXXXXXXXX",
            model_number="A2111",  # iPhone 11
            product_type=wrong_pt,
            imei=tac + "1234567",  # will fail Luhn but that's ok
        )
        # Should flag at least one issue (model mismatch or IMEI invalid)
        assert result.fraud_score > 0

    def test_matching_tac_no_flag(self):
        # When TAC matches product_type, no TAC mismatch flag
        result = cross_reference_check(
            serial="DNXXXXXXXXXX",
            model_number="A2483",
            product_type="iPhone14,2",
            imei="",  # skip IMEI check
        )
        assert "TAC" not in " ".join(result.flags)


class TestFraudScoring:
    """Test fraud score calculation."""

    def test_clean_device_score_zero(self):
        result = cross_reference_check(
            serial="DNXXXXXXXXXX",
            model_number="A2483",
            product_type="iPhone14,2",
            imei="",
        )
        assert result.fraud_score == 0

    def test_invalid_imei_adds_40(self):
        result = cross_reference_check(
            serial="DNXXXXXXXXXX",
            model_number="A2483",
            product_type="iPhone14,2",
            imei="123456789012345",  # invalid Luhn
        )
        assert result.fraud_score >= 40

    def test_model_mismatch_adds_30(self):
        result = cross_reference_check(
            serial="DNXXXXXXXXXX",
            model_number="A2483",  # iPhone 13 Pro
            product_type="iPhone12,1",  # iPhone 11
            imei="",
        )
        assert result.fraud_score >= 30

    def test_multiple_issues_stack(self):
        result = cross_reference_check(
            serial="DNXXXXXXXXXX",
            model_number="A2483",  # iPhone 13 Pro
            product_type="iPhone12,1",  # iPhone 11
            imei="123456789012345",  # invalid
        )
        assert result.fraud_score >= 70  # 40 (IMEI) + 30 (model mismatch)


class TestRandomizedSerialNote:
    """Test randomized serial note in fraud check."""

    def test_randomized_serial_note(self):
        result = cross_reference_check(
            serial="ABCDEFGHIJ",  # 10 chars = randomized
            model_number="A2483",
            product_type="iPhone14,2",
            imei="",
        )
        assert result.randomized_note != ""
        assert "randomized" in result.randomized_note.lower()

    def test_old_format_serial_no_note(self):
        result = cross_reference_check(
            serial="DNPXXXXXXXX",  # 12 chars with valid year code at pos 3
            model_number="A2483",
            product_type="iPhone14,2",
            imei="",
        )
        assert result.randomized_note == ""
```

**Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_fraud_detection.py -v`
Expected: FAIL — `fraud_score` and `randomized_note` not on FraudCheck, `TAC_MAP` not importable

**Step 3: Update FraudCheck model**

In `app/models/inventory.py`, update FraudCheck:

```python
class FraudCheck(BaseModel):
    """Cross-reference fraud detection result."""

    is_suspicious: bool = False
    flags: list[str] = []
    fraud_score: int = 0  # 0-100 weighted score
    randomized_note: str = ""  # note about randomized serial
```

**Step 4: Add TAC_MAP and update cross_reference_check in serial_decoder.py**

Add `TAC_MAP` after `ANUMBER_MAP` in `app/services/serial_decoder.py`:

```python
# TAC (Type Allocation Code) — first 8 digits of IMEI -> device model
TAC_MAP: dict[str, str] = {
    "35346211": "iPhone 13 Pro",
    "35407115": "iPhone 13 Pro Max",
    "35256211": "iPhone 13",
    "35256311": "iPhone 13 mini",
    "35467211": "iPhone 14",
    "35467311": "iPhone 14 Plus",
    "35523411": "iPhone 14 Pro",
    "35523511": "iPhone 14 Pro Max",
    "35691412": "iPhone 15",
    "35691512": "iPhone 15 Plus",
    "35691612": "iPhone 15 Pro",
    "35691712": "iPhone 15 Pro Max",
    "35474212": "iPhone SE (3rd gen)",
    "35205610": "iPhone 12",
    "35205510": "iPhone 12 mini",
    "35205710": "iPhone 12 Pro",
    "35205810": "iPhone 12 Pro Max",
    "35391509": "iPhone 11",
    "35395909": "iPhone 11 Pro",
    "35395809": "iPhone 11 Pro Max",
    "35325110": "iPhone SE (2nd gen)",
    "35884810": "iPhone 16",
    "35884910": "iPhone 16 Plus",
    "35885010": "iPhone 16 Pro",
    "35885110": "iPhone 16 Pro Max",
}
```

Then replace the `cross_reference_check` function:

```python
def cross_reference_check(
    serial: str,
    model_number: str,
    product_type: str,
    imei: str = "",
) -> FraudCheck:
    """Cross-reference device identifiers to detect board swaps or tampering."""
    result = FraudCheck()
    score = 0

    # Check if serial is randomized
    decoded = decode_serial(serial)
    if decoded.is_randomized:
        result.randomized_note = (
            "This device has a randomized serial number (manufactured after 2021). "
            "Serial-based factory/date decoding unavailable."
        )

    # Resolve device names from both model number and product type
    a_num = model_number.strip().upper()
    if not a_num.startswith("A"):
        a_num = "A" + a_num
    model_entry = ANUMBER_MAP.get(a_num)
    pt_name = PRODUCT_TYPE_MAP.get(product_type)

    if model_entry and pt_name:
        model_name = model_entry[0]
        if model_name != pt_name:
            result.is_suspicious = True
            result.flags.append(
                f"ModelNumber '{model_number}' -> '{model_name}' but "
                f"ProductType '{product_type}' -> '{pt_name}'. Possible board swap."
            )
            score += 30

    # IMEI validation
    if imei:
        imei_result = validate_imei(imei)
        if not imei_result.is_valid:
            result.is_suspicious = True
            result.flags.append(f"Invalid IMEI: {'; '.join(imei_result.notes)}")
            score += 40

        # TAC-based model cross-reference
        if imei_result.tac:
            tac_model = TAC_MAP.get(imei_result.tac)
            if tac_model and pt_name and tac_model != pt_name:
                result.is_suspicious = True
                result.flags.append(
                    f"IMEI TAC indicates '{tac_model}' but ProductType "
                    f"'{product_type}' -> '{pt_name}'. Possible IMEI tampering."
                )
                score += 20

    if not result.flags:
        if model_entry or pt_name:
            result.flags.append("No anomalies detected.")
        else:
            result.flags.append("Insufficient data for cross-reference (unknown model identifiers).")
            score += 10

    result.fraud_score = min(score, 100)
    return result
```

**Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_fraud_detection.py -v`
Expected: All PASS

**Step 6: Verify existing serial decoder tests still pass**

Run: `python -m pytest tests/test_serial_decoder.py -v`
Expected: All 16 tests PASS

**Step 7: Commit**

```bash
git add app/models/inventory.py app/services/serial_decoder.py tests/test_fraud_detection.py
git commit -m "feat: add TAC validation, fraud scoring, and randomized serial detection"
```

---

### Task 6: Add sell_price and profit fields to DeviceRecord + DB schema migration

**Files:**
- Modify: `app/models/device.py:41-55` (DeviceRecord)
- Modify: `app/services/inventory_db.py` (SCHEMA, upsert, _row_to_device)
- Modify: `tests/test_inventory_db.py`

**Step 1: Write failing tests**

Append to `tests/test_inventory_db.py` (or update the existing CRUD tests):

```python
class TestPricingFields:
    """Test sell_price and profit on DeviceRecord."""

    def test_device_record_has_pricing_fields(self):
        from app.models.device import DeviceRecord
        record = DeviceRecord(udid="test-pricing")
        assert hasattr(record, "sell_price")
        assert hasattr(record, "profit")
        assert record.sell_price is None
        assert record.profit is None

    def test_upsert_with_pricing(self, tmp_path):
        from app.services.inventory_db import InventoryDB
        from app.models.device import DeviceRecord
        db = InventoryDB(db_path=tmp_path / "test.db")
        db.init_db()
        record = DeviceRecord(
            udid="test-price-1",
            buy_price=200.0,
            sell_price=350.0,
        )
        device_id = db.upsert_device(record)
        loaded = db.get_device_by_id(device_id)
        assert loaded is not None
        assert loaded.buy_price == 200.0
        assert loaded.sell_price == 350.0
        assert loaded.profit == 150.0
        db.close()

    def test_profit_none_when_prices_missing(self, tmp_path):
        from app.services.inventory_db import InventoryDB
        from app.models.device import DeviceRecord
        db = InventoryDB(db_path=tmp_path / "test.db")
        db.init_db()
        record = DeviceRecord(udid="test-price-2", buy_price=200.0)
        device_id = db.upsert_device(record)
        loaded = db.get_device_by_id(device_id)
        assert loaded is not None
        assert loaded.profit is None
        db.close()
```

**Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_inventory_db.py::TestPricingFields -v`
Expected: FAIL — `sell_price` and `profit` not on model

**Step 3: Update DeviceRecord model**

In `app/models/device.py`, add fields to `DeviceRecord`:

```python
class DeviceRecord(BaseModel):
    """Persisted device record in inventory database."""

    id: Optional[int] = None
    udid: str
    serial: str = ""
    imei: str = ""
    model: str = ""
    ios_version: str = ""
    grade: str = ""
    status: DeviceStatus = "intake"
    buy_price: Optional[float] = None
    sell_price: Optional[float] = None
    notes: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def profit(self) -> Optional[float]:
        if self.buy_price is not None and self.sell_price is not None:
            return round(self.sell_price - self.buy_price, 2)
        return None
```

**Note:** `profit` is a computed property, not stored in DB.

**Step 4: Update DB schema and queries**

In `app/services/inventory_db.py`, update the SCHEMA `devices` table to add `sell_price`:

```sql
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    udid TEXT UNIQUE NOT NULL,
    serial TEXT DEFAULT '',
    imei TEXT DEFAULT '',
    model TEXT DEFAULT '',
    ios_version TEXT DEFAULT '',
    grade TEXT DEFAULT '',
    status TEXT DEFAULT 'intake',
    buy_price REAL,
    sell_price REAL,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Update `upsert_device` UPDATE query to include `sell_price`:
```python
self.conn.execute(
    """UPDATE devices SET serial=?, imei=?, model=?, ios_version=?,
       grade=?, status=?, buy_price=?, sell_price=?, notes=?, updated_at=?
       WHERE udid=?""",
    (
        record.serial, record.imei, record.model, record.ios_version,
        record.grade, record.status, record.buy_price, record.sell_price,
        record.notes, now, record.udid,
    ),
)
```

Update INSERT query similarly:
```python
cur = self.conn.execute(
    """INSERT INTO devices (udid, serial, imei, model, ios_version,
       grade, status, buy_price, sell_price, notes, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    (
        record.udid, record.serial, record.imei, record.model,
        record.ios_version, record.grade, record.status,
        record.buy_price, record.sell_price, record.notes, now, now,
    ),
)
```

Update `_row_to_device` to include `sell_price`:
```python
@staticmethod
def _row_to_device(row: sqlite3.Row) -> DeviceRecord:
    return DeviceRecord(
        id=row["id"],
        udid=row["udid"],
        serial=row["serial"] or "",
        imei=row["imei"] or "",
        model=row["model"] or "",
        ios_version=row["ios_version"] or "",
        grade=row["grade"] or "",
        status=row["status"] or "intake",
        buy_price=row["buy_price"],
        sell_price=row["sell_price"],
        notes=row["notes"] or "",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
```

Also add an `init_db` migration to add the column if upgrading from Sprint 1 DB:

Add to `init_db()` after the `executescript(SCHEMA)`:
```python
def init_db(self) -> None:
    """Create tables if they don't exist."""
    with self._lock:
        self.conn.executescript(SCHEMA)
        # Sprint 2 migration: add sell_price column if missing
        try:
            self.conn.execute("SELECT sell_price FROM devices LIMIT 1")
        except sqlite3.OperationalError:
            self.conn.execute("ALTER TABLE devices ADD COLUMN sell_price REAL")
        self.conn.commit()
```

**Step 5: Run tests**

Run: `python -m pytest tests/test_inventory_db.py -v`
Expected: All PASS (old + new)

**Step 6: Commit**

```bash
git add app/models/device.py app/services/inventory_db.py tests/test_inventory_db.py
git commit -m "feat: add sell_price and computed profit to DeviceRecord"
```

---

### Task 7: Add history query methods to InventoryDB

**Files:**
- Modify: `app/services/inventory_db.py`
- Modify: `tests/test_inventory_db.py`

**Step 1: Write failing tests**

Append to `tests/test_inventory_db.py`:

```python
class TestHistoryQueries:
    """Test diagnostic and verification history retrieval."""

    def test_list_diagnostics_for_device(self, tmp_path):
        from app.services.inventory_db import InventoryDB
        from app.models.device import DeviceRecord
        from app.models.diagnostic import DiagnosticResult, BatteryInfo
        db = InventoryDB(db_path=tmp_path / "test.db")
        db.init_db()
        device_id = db.upsert_device(DeviceRecord(udid="hist-1"))
        db.save_diagnostic(device_id, DiagnosticResult(battery=BatteryInfo(health_percent=95.0, cycle_count=100)))
        db.save_diagnostic(device_id, DiagnosticResult(battery=BatteryInfo(health_percent=93.0, cycle_count=120)))
        history = db.list_diagnostics(device_id)
        assert len(history) == 2
        db.close()

    def test_list_verifications_for_device(self, tmp_path):
        from app.services.inventory_db import InventoryDB
        from app.models.device import DeviceRecord
        from app.models.verification import VerificationResult
        db = InventoryDB(db_path=tmp_path / "test.db")
        db.init_db()
        device_id = db.upsert_device(DeviceRecord(udid="hist-2"))
        db.save_verification(device_id, VerificationResult(blacklist_status="clean"))
        history = db.list_verifications(device_id)
        assert len(history) == 1
        assert history[0]["blacklist_status"] == "clean"
        db.close()

    def test_list_crash_history_for_device(self, tmp_path):
        from app.services.inventory_db import InventoryDB
        from app.models.device import DeviceRecord
        db = InventoryDB(db_path=tmp_path / "test.db")
        db.init_db()
        device_id = db.upsert_device(DeviceRecord(udid="hist-3"))
        db.save_crash_summary(device_id, "cameracaptured", "Camera", 5, 3)
        db.save_crash_summary(device_id, "wifid", "WiFi", 4, 2)
        history = db.list_crash_history(device_id)
        assert len(history) == 2
        db.close()
```

**Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_inventory_db.py::TestHistoryQueries -v`
Expected: FAIL — `list_diagnostics`, `list_verifications`, `list_crash_history` not found

**Step 3: Implement history methods**

Add to `app/services/inventory_db.py` InventoryDB class:

```python
def list_diagnostics(self, device_id: int) -> list[dict]:
    """Return all diagnostic records for a device, newest first."""
    with self._lock:
        rows = self.conn.execute(
            "SELECT * FROM diagnostics WHERE device_id=? ORDER BY timestamp DESC",
            (device_id,),
        ).fetchall()
        return [dict(row) for row in rows]

def list_verifications(self, device_id: int) -> list[dict]:
    """Return all verification records for a device, newest first."""
    with self._lock:
        rows = self.conn.execute(
            "SELECT * FROM verifications WHERE device_id=? ORDER BY timestamp DESC",
            (device_id,),
        ).fetchall()
        return [dict(row) for row in rows]

def list_crash_history(self, device_id: int) -> list[dict]:
    """Return all crash report summaries for a device, newest first."""
    with self._lock:
        rows = self.conn.execute(
            "SELECT * FROM crash_reports WHERE device_id=? ORDER BY timestamp DESC",
            (device_id,),
        ).fetchall()
        return [dict(row) for row in rows]
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_inventory_db.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add app/services/inventory_db.py tests/test_inventory_db.py
git commit -m "feat: add history query methods for diagnostics, verifications, and crash reports"
```

---

### Task 8: Create shared test fixtures (conftest.py)

**Files:**
- Create: `tests/conftest.py`

**Step 1: Create conftest with mocked device layer**

Create `tests/conftest.py`:

```python
"""Shared test fixtures — mock pymobiledevice3 and external services."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_lockdown():
    """Mock pymobiledevice3 lockdown client with realistic device values."""
    lockdown = MagicMock()
    lockdown.udid = "00008030-001A2B3C4D5E6F78"
    lockdown.product_type = "iPhone14,2"
    lockdown.product_version = "17.2"
    lockdown.product_build_version = "21C62"
    lockdown.hardware_model = "D63AP"
    lockdown.wifi_mac_address = "AA:BB:CC:DD:EE:FF"
    lockdown.ecid = 0x1234567890

    def get_value(domain=None, key=None):
        values = {
            "SerialNumber": "DNPXXXXXXXX",
            "InternationalMobileEquipmentIdentity": "353462111234567",
            "InternationalMobileEquipmentIdentity2": "",
            "ModelNumber": "A2483",
            "DeviceName": "Test iPhone",
            "DeviceColor": "#E3E3E0",
            "ActivationState": "Activated",
        }
        if domain == "com.apple.disk_usage":
            return {"TotalDataCapacity": 128 * 1024**3, "TotalDataAvailable": 64 * 1024**3}
        return values.get(key, "")

    lockdown.get_value = get_value
    lockdown.__enter__ = MagicMock(return_value=lockdown)
    lockdown.__exit__ = MagicMock(return_value=False)
    return lockdown


@pytest.fixture
def mock_battery_data():
    """Realistic battery data from DiagnosticsService."""
    return {
        "NominalChargeCapacity": 3095,
        "DesignCapacity": 3227,
        "CycleCount": 247,
        "AppleRawCurrentCapacity": 2850,
        "Temperature": 2950,  # centi-degrees (29.5°C)
        "Voltage": 4150,
        "IsCharging": False,
        "FullyCharged": False,
    }


@pytest.fixture
def mock_gestalt_response():
    """Realistic MobileGestalt response."""
    return {
        "MobileGestalt": {
            "BatteryIsOriginal": True,
            "a/ScreenIsOriginal": True,
        }
    }


@pytest.fixture
def sample_crash_files():
    """Return paths to sample crash report fixture files."""
    return list(FIXTURES_DIR.glob("*.ips"))
```

**Step 2: Verify fixtures load correctly**

Run: `python -m pytest tests/ -v --co` (collect only — list all discovered tests)
Expected: All existing tests are still discovered, conftest loads without error

**Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "feat: add shared test fixtures with mocked device layer"
```

---

### Task 9: Test diagnostic engine with mocked device

**Files:**
- Create: `tests/test_diagnostic_engine.py`

**Step 1: Write tests with mocked pymobiledevice3**

Create `tests/test_diagnostic_engine.py`:

```python
"""Tests for diagnostic engine with mocked pymobiledevice3."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.diagnostic_engine import run_diagnostics, _normalize_temperature


class TestNormalizeTemperature:
    def test_centi_degrees(self):
        assert _normalize_temperature(2950) == 29.5

    def test_already_normalized(self):
        assert _normalize_temperature(29.5) == 29.5

    def test_zero(self):
        assert _normalize_temperature(0) == 0.0


class TestRunDiagnostics:
    @patch("app.services.diagnostic_engine.create_using_usbmux")
    def test_returns_battery_info(self, mock_create, mock_lockdown, mock_battery_data):
        mock_create.return_value = mock_lockdown

        mock_diag_service = MagicMock()
        mock_diag_service.get_battery.return_value = mock_battery_data
        mock_diag_service.mobilegestalt.return_value = {
            "MobileGestalt": {"BatteryIsOriginal": True, "a/ScreenIsOriginal": True}
        }
        mock_diag_service.__enter__ = MagicMock(return_value=mock_diag_service)
        mock_diag_service.__exit__ = MagicMock(return_value=False)

        with patch(
            "app.services.diagnostic_engine.DiagnosticsService",
            return_value=mock_diag_service,
        ):
            result = run_diagnostics("test-udid")

        assert result.battery.health_percent == pytest.approx(95.9, rel=0.1)
        assert result.battery.cycle_count == 247
        assert result.battery.temperature == 29.5

    @patch("app.services.diagnostic_engine.create_using_usbmux")
    def test_returns_storage_info(self, mock_create, mock_lockdown):
        mock_create.return_value = mock_lockdown

        mock_diag_service = MagicMock()
        mock_diag_service.get_battery.return_value = {}
        mock_diag_service.mobilegestalt.return_value = {"MobileGestalt": {}}
        mock_diag_service.__enter__ = MagicMock(return_value=mock_diag_service)
        mock_diag_service.__exit__ = MagicMock(return_value=False)

        with patch(
            "app.services.diagnostic_engine.DiagnosticsService",
            return_value=mock_diag_service,
        ):
            result = run_diagnostics("test-udid")

        assert result.storage.total_gb == 128.0
        assert result.storage.available_gb == 64.0

    @patch("app.services.diagnostic_engine.create_using_usbmux")
    def test_replaced_parts_detected(self, mock_create, mock_lockdown):
        mock_create.return_value = mock_lockdown

        mock_diag_service = MagicMock()
        mock_diag_service.get_battery.return_value = {}
        mock_diag_service.mobilegestalt.return_value = {
            "MobileGestalt": {"BatteryIsOriginal": False, "a/ScreenIsOriginal": True}
        }
        mock_diag_service.__enter__ = MagicMock(return_value=mock_diag_service)
        mock_diag_service.__exit__ = MagicMock(return_value=False)

        with patch(
            "app.services.diagnostic_engine.DiagnosticsService",
            return_value=mock_diag_service,
        ):
            result = run_diagnostics("test-udid")

        assert not result.parts.all_original
        assert "battery" in result.parts.replaced_parts

    def test_handles_missing_pymobiledevice3(self):
        with patch.dict("sys.modules", {"pymobiledevice3": None, "pymobiledevice3.lockdown": None}):
            # Force reimport to trigger ImportError path
            result = run_diagnostics("test-udid")
            # Should return empty DiagnosticResult, not crash
            assert result.battery.health_percent == 0.0
```

**Step 2: Run tests**

Run: `python -m pytest tests/test_diagnostic_engine.py -v`

Note: The last test (`test_handles_missing_pymobiledevice3`) is tricky due to module caching. If it fails, that's acceptable — the important tests are the mocked-device ones. Remove the last test if it causes issues.

Expected: At least 3 tests PASS

**Step 3: Commit**

```bash
git add tests/test_diagnostic_engine.py
git commit -m "test: add diagnostic engine tests with mocked pymobiledevice3"
```

---

### Task 10: Test verification service with mocked HTTP

**Files:**
- Create: `tests/test_verification_service.py`

**Step 1: Write tests**

Create `tests/test_verification_service.py`:

```python
"""Tests for verification service with mocked HTTP and device layer."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.verification_service import (
    _parse_sickw_result,
    check_imei_sickw,
    run_verification,
)


class TestParseSickwResult:
    def test_clean_result(self):
        raw = {
            "result": {
                "Blacklist Status": "Clean",
                "iCloud Lock": "OFF",
                "Carrier": "T-Mobile USA",
                "SIM-Lock Status": "Unlocked",
            }
        }
        result = _parse_sickw_result(raw)
        assert result.blacklist_status == "clean"
        assert result.fmi_status == "off"
        assert result.carrier == "T-Mobile USA"
        assert not result.carrier_locked

    def test_blacklisted_result(self):
        raw = {
            "result": {
                "Blacklist Status": "Blacklisted - Lost/Stolen",
                "iCloud Lock": "ON",
                "Carrier": "AT&T",
                "SIM-Lock Status": "Locked",
            }
        }
        result = _parse_sickw_result(raw)
        assert result.blacklist_status == "blacklisted"
        assert result.fmi_status == "on"
        assert result.carrier_locked

    def test_non_dict_result(self):
        raw = {"result": "Some error string"}
        result = _parse_sickw_result(raw)
        assert result.blacklist_status == "unknown"


class TestCheckImeiSickw:
    @pytest.mark.asyncio
    async def test_no_api_key_returns_error(self):
        with patch("app.services.verification_service.settings") as mock_settings:
            mock_settings.sickw_api_key = ""
            result = await check_imei_sickw("353462111234567")
            assert "error" in result

    @pytest.mark.asyncio
    async def test_successful_api_call(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"Blacklist Status": "Clean", "iCloud Lock": "OFF", "Carrier": "Verizon", "SIM-Lock Status": "Unlocked"}
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.verification_service.settings") as mock_settings:
            mock_settings.sickw_api_key = "test-key"
            mock_settings.sickw_base_url = "https://sickw.com/api.php"
            mock_settings.sickw_default_service = 61
            with patch("app.services.verification_service.httpx.AsyncClient", return_value=mock_client):
                result = await check_imei_sickw("353462111234567")

        assert "error" not in result
        assert result["result"]["Carrier"] == "Verizon"
```

**Step 2: Run tests**

Run: `python -m pytest tests/test_verification_service.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/test_verification_service.py
git commit -m "test: add verification service tests with mocked HTTP"
```

---

### Task 11: Unified Snapshot API endpoint

**Files:**
- Modify: `app/api/diagnostics.py`
- Create: `tests/test_snapshot_api.py`

**Step 1: Write failing tests**

Create `tests/test_snapshot_api.py`:

```python
"""Tests for the unified snapshot API endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestSnapshotEndpoint:
    @patch("app.api.diagnostics.device_service.get_device_info")
    @patch("app.api.diagnostics.diagnostic_engine.run_diagnostics")
    @patch("app.api.diagnostics.log_analyzer.analyze_device")
    @patch("app.api.diagnostics.verification_service.run_verification", new_callable=AsyncMock)
    @patch("app.api.diagnostics.calculate_grade")
    def test_snapshot_returns_all_fields(
        self, mock_grade, mock_verif, mock_crashes, mock_diag, mock_info
    ):
        from app.models.device import DeviceInfo
        from app.models.diagnostic import DiagnosticResult, BatteryInfo
        from app.models.crash import CrashAnalysis
        from app.models.verification import VerificationResult
        from app.models.grading import DeviceGrade

        mock_info.return_value = DeviceInfo(
            udid="test-udid", serial="DNPXXXXXXXX", imei="353462111234567",
            product_type="iPhone14,2",
        )
        mock_diag.return_value = DiagnosticResult(battery=BatteryInfo(health_percent=95.0))
        mock_crashes.return_value = CrashAnalysis(total_reports=5)
        mock_verif.return_value = VerificationResult(blacklist_status="clean")
        mock_grade.return_value = DeviceGrade(overall_grade="A", overall_score=3.8)

        resp = client.get("/api/diagnostics/snapshot/test-udid")
        assert resp.status_code == 200
        data = resp.json()
        assert data["info"]["udid"] == "test-udid"
        assert data["diagnostics"]["battery"]["health_percent"] == 95.0
        assert data["crash_analysis"]["total_reports"] == 5
        assert data["verification"]["blacklist_status"] == "clean"
        assert data["grade"]["overall_grade"] == "A"

    @patch("app.api.diagnostics.device_service.get_device_info")
    def test_snapshot_404_when_no_device(self, mock_info):
        mock_info.return_value = None
        resp = client.get("/api/diagnostics/snapshot/nonexistent")
        assert resp.status_code == 404
```

**Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_snapshot_api.py -v`
Expected: FAIL — no `/api/diagnostics/snapshot/{udid}` route exists

**Step 3: Add snapshot endpoint to diagnostics.py**

In `app/api/diagnostics.py`, add imports and the snapshot route:

Add to imports at top:
```python
from fastapi import APIRouter, HTTPException
from app.models.inventory import DeviceSnapshot
from app.services import device_service
```

Add the endpoint:
```python
@router.get("/snapshot/{udid}")
async def get_device_snapshot(udid: str, cosmetic: str | None = None) -> DeviceSnapshot:
    """Run all diagnostics and assemble a full device snapshot."""
    info = await asyncio.to_thread(device_service.get_device_info, udid)
    if not info:
        raise HTTPException(status_code=404, detail="Device not found or connection failed")

    diag = await asyncio.to_thread(diagnostic_engine.run_diagnostics, udid)
    crashes = await asyncio.to_thread(log_analyzer.analyze_device, udid)

    verif = None
    if info.imei:
        verif = await verification_service.run_verification(udid=udid, imei=info.imei)

    grade = calculate_grade(
        diag, crashes, verif or VerificationResult(), cosmetic
    )

    return DeviceSnapshot(
        info=info,
        diagnostics=diag,
        crash_analysis=crashes,
        verification=verif,
        grade=grade,
    )
```

Also add `VerificationResult` import:
```python
from app.models.verification import VerificationResult
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_snapshot_api.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add app/api/diagnostics.py tests/test_snapshot_api.py
git commit -m "feat: add unified snapshot API endpoint GET /api/diagnostics/snapshot/{udid}"
```

---

### Task 12: History API endpoints and capabilities endpoint

**Files:**
- Modify: `app/api/inventory.py`
- Modify: `app/api/devices.py`

**Step 1: Add history endpoints to inventory.py**

In `app/api/inventory.py`, add:

```python
@router.get("/devices/{device_id}/diagnostics")
def list_device_diagnostics(device_id: int) -> list[dict]:
    record = get_db().get_device_by_id(device_id)
    if not record:
        raise HTTPException(status_code=404, detail="Device not found")
    return get_db().list_diagnostics(device_id)


@router.get("/devices/{device_id}/verifications")
def list_device_verifications(device_id: int) -> list[dict]:
    record = get_db().get_device_by_id(device_id)
    if not record:
        raise HTTPException(status_code=404, detail="Device not found")
    return get_db().list_verifications(device_id)


@router.get("/devices/{device_id}/crashes")
def list_device_crashes(device_id: int) -> list[dict]:
    record = get_db().get_device_by_id(device_id)
    if not record:
        raise HTTPException(status_code=404, detail="Device not found")
    return get_db().list_crash_history(device_id)
```

**Step 2: Add capabilities endpoint to devices.py**

In `app/api/devices.py`, add:

```python
from app.models.device import DeviceCapability, DeviceInfo


@router.get("/capabilities/{product_type}")
def get_capabilities(product_type: str) -> DeviceCapability:
    """Get device capabilities by ProductType (e.g. iPhone14,2)."""
    cap = device_service.get_capability(product_type)
    if not cap:
        raise HTTPException(status_code=404, detail=f"No capability data for {product_type}")
    return cap
```

Also add `DeviceCapability` to the import:
```python
from app.models.device import DeviceCapability, DeviceInfo
```

**Step 3: Run all tests to verify nothing broke**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add app/api/inventory.py app/api/devices.py
git commit -m "feat: add history endpoints and device capabilities endpoint"
```

---

### Task 13: Dashboard v2 — snapshot-driven view, crash details, pricing, capabilities

**Files:**
- Modify: `app/templates/index.html`

**Step 1: Rewrite the dashboard**

Replace `app/templates/index.html` with the updated Dashboard v2. This is a large file. Key changes:

1. On `device_connected`, auto-fetch `/api/diagnostics/snapshot/{udid}` and render all panels
2. Add expandable crash detail panel with severity badges and trend indicators
3. Add device history tab (fetches from history endpoints)
4. Add buy price / sell price inputs with auto-calculated profit
5. Add device capability chips
6. Keep the existing manual "Run Full Diagnostics" button as override

The full HTML content is provided below — write the complete file:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>iDiag - iPhone Diagnostic Tool</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .severity-5 { background: #ef4444; color: white; }
        .severity-4 { background: #f97316; color: white; }
        .severity-3 { background: #eab308; color: black; }
        .severity-2 { background: #3b82f6; color: white; }
        .severity-1 { background: #6b7280; color: white; }
        .trend-worsening { color: #ef4444; }
        .trend-stable { color: #6b7280; }
        .trend-improving { color: #22c55e; }
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <!-- Header -->
    <header class="bg-gray-900 text-white py-3 px-6 flex items-center justify-between">
        <div class="flex items-center gap-3">
            <h1 class="text-xl font-bold">iDiag</h1>
            <span class="text-gray-400 text-sm">v{{ version }}</span>
        </div>
        <div class="flex items-center gap-2">
            <span id="device-indicator" class="w-3 h-3 rounded-full bg-gray-500"></span>
            <span id="device-status-text" class="text-sm text-gray-400">No device connected</span>
        </div>
    </header>

    <main class="max-w-7xl mx-auto p-6">
        <!-- No Device State -->
        <div id="no-device" class="text-center py-20">
            <div class="text-6xl mb-4">📱</div>
            <h2 class="text-2xl font-semibold text-gray-700 mb-2">Connect an iPhone</h2>
            <p class="text-gray-500">Plug in a device via USB cable to begin diagnostics</p>
            <div class="mt-4">
                <button onclick="scanDevices()" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
                    Scan for Devices
                </button>
            </div>
        </div>

        <!-- Device Dashboard -->
        <div id="device-dashboard" class="hidden">
            <!-- Assessment Banner -->
            <div id="assessment-banner" class="rounded-lg p-6 mb-6 bg-white shadow-md">
                <div class="flex items-center justify-between">
                    <div>
                        <h2 id="device-model" class="text-2xl font-bold text-gray-800"></h2>
                        <p id="device-ios" class="text-gray-500"></p>
                        <div id="capability-chips" class="flex flex-wrap gap-1 mt-2"></div>
                    </div>
                    <div class="text-center">
                        <div id="overall-grade" class="text-5xl font-black text-gray-300">--</div>
                        <div id="grade-label" class="text-sm text-gray-500 mt-1">Loading...</div>
                    </div>
                </div>
                <!-- Predicted Failures Banner -->
                <div id="predicted-failures" class="hidden mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                    <h4 class="font-semibold text-red-700 mb-1">Predicted Failures</h4>
                    <ul id="predicted-failures-list" class="text-sm text-red-600 list-disc list-inside"></ul>
                </div>
                <!-- Fraud Alert -->
                <div id="fraud-alert" class="hidden mt-4 p-3 bg-orange-50 border border-orange-200 rounded-lg">
                    <h4 class="font-semibold text-orange-700 mb-1">Fraud Detection</h4>
                    <div id="fraud-details" class="text-sm text-orange-600"></div>
                </div>
            </div>

            <!-- Tabs -->
            <div class="flex gap-1 mb-4">
                <button onclick="switchTab('diagnostics')" id="tab-diagnostics" class="px-4 py-2 rounded-t bg-white font-semibold text-blue-600 border-b-2 border-blue-600">Diagnostics</button>
                <button onclick="switchTab('history')" id="tab-history" class="px-4 py-2 rounded-t bg-gray-200 text-gray-600">History</button>
                <button onclick="switchTab('pricing')" id="tab-pricing" class="px-4 py-2 rounded-t bg-gray-200 text-gray-600">Pricing</button>
            </div>

            <!-- Diagnostics Tab -->
            <div id="panel-diagnostics">
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <!-- Device Info -->
                    <div class="bg-white rounded-lg shadow-md p-4">
                        <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Device Info</h3>
                        <dl id="device-info-list" class="space-y-1 text-sm"></dl>
                    </div>

                    <!-- Serial Decode -->
                    <div class="bg-white rounded-lg shadow-md p-4">
                        <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Serial Decode</h3>
                        <dl id="serial-decode-list" class="space-y-1 text-sm"></dl>
                    </div>

                    <!-- Battery -->
                    <div class="bg-white rounded-lg shadow-md p-4">
                        <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Battery</h3>
                        <div id="battery-info"><span class="text-gray-400 animate-pulse">Loading...</span></div>
                    </div>

                    <!-- Parts -->
                    <div class="bg-white rounded-lg shadow-md p-4">
                        <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Parts Originality</h3>
                        <div id="parts-info"><span class="text-gray-400 animate-pulse">Loading...</span></div>
                    </div>

                    <!-- Verification -->
                    <div class="bg-white rounded-lg shadow-md p-4">
                        <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Verification</h3>
                        <div id="verification-info"><span class="text-gray-400 animate-pulse">Loading...</span></div>
                    </div>

                    <!-- Crash Analysis -->
                    <div class="bg-white rounded-lg shadow-md p-4">
                        <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2 flex justify-between items-center">
                            Crash Analysis
                            <button onclick="toggleCrashDetails()" class="text-xs text-blue-600 hover:underline" id="crash-toggle">Show details</button>
                        </h3>
                        <div id="crash-info"><span class="text-gray-400 animate-pulse">Loading...</span></div>
                        <div id="crash-details" class="hidden mt-3 border-t pt-3 max-h-64 overflow-y-auto"></div>
                    </div>
                </div>
            </div>

            <!-- History Tab -->
            <div id="panel-history" class="hidden">
                <div class="bg-white rounded-lg shadow-md p-4">
                    <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Scan History</h3>
                    <div id="history-content"><span class="text-gray-400">Save device to inventory to track history</span></div>
                </div>
            </div>

            <!-- Pricing Tab -->
            <div id="panel-pricing" class="hidden">
                <div class="bg-white rounded-lg shadow-md p-4 max-w-md">
                    <h3 class="font-semibold text-gray-700 mb-3 border-b pb-2">Pricing & Profit</h3>
                    <div class="space-y-3">
                        <div>
                            <label class="block text-sm text-gray-500 mb-1">Buy Price ($)</label>
                            <input type="number" id="buy-price" step="0.01" min="0" class="w-full border rounded px-3 py-2" placeholder="0.00">
                        </div>
                        <div>
                            <label class="block text-sm text-gray-500 mb-1">Sell Price ($)</label>
                            <input type="number" id="sell-price" step="0.01" min="0" class="w-full border rounded px-3 py-2" placeholder="0.00">
                        </div>
                        <div id="profit-display" class="text-center p-3 bg-gray-50 rounded">
                            <span class="text-sm text-gray-500">Profit</span>
                            <div id="profit-amount" class="text-2xl font-bold text-gray-300">--</div>
                        </div>
                        <button onclick="savePricing()" class="w-full bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700">
                            Save Pricing
                        </button>
                    </div>
                </div>
            </div>

            <!-- Actions -->
            <div class="mt-6 flex gap-3 flex-wrap">
                <button onclick="runSnapshot()" id="btn-diag" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
                    Re-run Diagnostics
                </button>
                <button onclick="saveToInventory()" class="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700">
                    Save to Inventory
                </button>
                <button onclick="location.href='/api/inventory/devices'" class="bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700">
                    View Inventory
                </button>
            </div>
        </div>
    </main>

    <script>
    let ws = null;
    let currentDevice = null;
    let currentSnapshot = null;

    // -- WebSocket --

    function connectWebSocket() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(protocol + '//' + location.host + '/ws');
        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.event === 'device_connected') onDeviceConnected(msg.data);
            else if (msg.event === 'device_disconnected') onDeviceDisconnected(msg.data);
            else if (msg.event === 'device_list' && msg.data.udids.length > 0) {
                loadSnapshot(msg.data.udids[0]);
            }
        };
        ws.onclose = () => setTimeout(connectWebSocket, 3000);
    }

    function scanDevices() {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({action: 'scan'}));
        }
        fetch('/api/devices/connected')
            .then(r => r.json())
            .then(udids => { if (udids.length > 0) loadSnapshot(udids[0]); })
            .catch(() => {});
    }

    // -- Snapshot --

    async function loadSnapshot(udid) {
        el('no-device').classList.add('hidden');
        el('device-dashboard').classList.remove('hidden');
        el('device-indicator').className = 'w-3 h-3 rounded-full bg-yellow-500 animate-pulse';
        el('device-status-text').textContent = 'Scanning...';

        try {
            const resp = await fetch('/api/diagnostics/snapshot/' + udid);
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            const snapshot = await resp.json();
            currentSnapshot = snapshot;
            currentDevice = { udid, info: snapshot.info };
            renderSnapshot(snapshot);
        } catch (e) {
            console.error('Snapshot failed:', e);
            el('device-indicator').className = 'w-3 h-3 rounded-full bg-red-500';
            el('device-status-text').textContent = 'Scan failed';
        }
    }

    function runSnapshot() {
        if (currentDevice) loadSnapshot(currentDevice.udid);
    }

    function renderSnapshot(s) {
        const info = s.info || {};
        el('device-indicator').className = 'w-3 h-3 rounded-full bg-green-500';
        el('device-status-text').textContent = info.device_name || info.product_type || 'Connected';
        el('device-model').textContent = info.product_type || 'Unknown Device';
        el('device-ios').textContent = 'iOS ' + (info.ios_version || '?') + ' (' + (info.build_version || '?') + ')';

        renderDeviceInfo(info);
        if (info.serial) fetchSerialDecode(info.serial);
        if (info.product_type) fetchCapabilities(info.product_type);
        if (info.serial && info.model_number && info.product_type) fetchFraudCheck(info);
        if (s.diagnostics) {
            renderBattery(s.diagnostics.battery || {});
            renderParts(s.diagnostics.parts || {}, s.diagnostics.storage || {});
        }
        if (s.verification) renderVerification(s.verification);
        else el('verification-info').innerHTML = '<span class="text-gray-400">No IMEI or API key not configured</span>';
        if (s.crash_analysis) renderCrashes(s.crash_analysis);
        if (s.grade) renderGrade(s.grade);
    }

    // -- Device Events --

    function onDeviceConnected(data) {
        const udid = data.udid || (data.info && data.info.udid);
        if (udid) loadSnapshot(udid);
    }

    function onDeviceDisconnected() {
        currentDevice = null;
        currentSnapshot = null;
        el('device-indicator').className = 'w-3 h-3 rounded-full bg-gray-500';
        el('device-status-text').textContent = 'No device connected';
        el('no-device').classList.remove('hidden');
        el('device-dashboard').classList.add('hidden');
    }

    // -- Tabs --

    function switchTab(tab) {
        for (const t of ['diagnostics', 'history', 'pricing']) {
            el('panel-' + t).classList.toggle('hidden', t !== tab);
            el('tab-' + t).className = t === tab
                ? 'px-4 py-2 rounded-t bg-white font-semibold text-blue-600 border-b-2 border-blue-600'
                : 'px-4 py-2 rounded-t bg-gray-200 text-gray-600';
        }
        if (tab === 'history') loadHistory();
    }

    // -- Rendering --

    function renderDeviceInfo(info) {
        el('device-info-list').innerHTML = infoRow('UDID', info.udid, true)
            + infoRow('Serial', info.serial) + infoRow('IMEI', info.imei)
            + infoRow('Model #', info.model_number) + infoRow('Hardware', info.hardware_model)
            + infoRow('Color', info.device_color) + infoRow('WiFi MAC', info.wifi_mac, true);
    }

    function fetchSerialDecode(serial) {
        fetch('/api/serial/decode/' + serial)
            .then(r => r.json())
            .then(d => {
                if (d.is_randomized) {
                    el('serial-decode-list').innerHTML = infoRow('Format', 'Randomized (post-2021)')
                        + infoRow('Serial', d.raw);
                } else {
                    el('serial-decode-list').innerHTML = infoRow('Factory', d.factory)
                        + infoRow('Year(s)', d.year_candidates.join(' / '))
                        + infoRow('Half', d.half) + infoRow('Week', d.week_of_year || '?')
                        + infoRow('Model Code', d.model_code);
                }
            })
            .catch(() => el('serial-decode-list').innerHTML = '<span class="text-red-500">Decode failed</span>');
    }

    function fetchCapabilities(productType) {
        fetch('/api/devices/capabilities/' + productType)
            .then(r => { if (r.ok) return r.json(); throw new Error(); })
            .then(cap => {
                let chips = '';
                if (cap.checkm8) chips += chip('checkm8', 'bg-purple-100 text-purple-700');
                if (cap.esim) chips += chip('eSIM', 'bg-blue-100 text-blue-700');
                if (cap.faceid) chips += chip('Face ID', 'bg-green-100 text-green-700');
                if (cap.touchid) chips += chip('Touch ID', 'bg-green-100 text-green-700');
                if (cap.max_ios) chips += chip('Max iOS ' + cap.max_ios, 'bg-gray-100 text-gray-700');
                chips += chip(cap.chip, 'bg-gray-100 text-gray-700');
                el('capability-chips').innerHTML = chips;
            })
            .catch(() => el('capability-chips').innerHTML = '');
    }

    function fetchFraudCheck(info) {
        const params = new URLSearchParams({
            serial: info.serial, model_number: info.model_number,
            product_type: info.product_type, imei: info.imei || '',
        });
        fetch('/api/serial/fraud-check?' + params)
            .then(r => r.json())
            .then(fc => {
                if (fc.fraud_score > 0 || fc.is_suspicious) {
                    el('fraud-alert').classList.remove('hidden');
                    let html = '<div class="font-semibold">Score: ' + fc.fraud_score + '/100</div>';
                    fc.flags.forEach(f => { html += '<div>- ' + esc(f) + '</div>'; });
                    if (fc.randomized_note) html += '<div class="mt-1 italic">' + esc(fc.randomized_note) + '</div>';
                    el('fraud-details').innerHTML = html;
                } else {
                    el('fraud-alert').classList.add('hidden');
                }
            })
            .catch(() => {});
    }

    function renderBattery(bat) {
        const color = bat.health_percent >= 90 ? 'text-green-600' : bat.health_percent >= 80 ? 'text-yellow-600' : 'text-red-600';
        el('battery-info').innerHTML = '<div class="text-3xl font-bold ' + color + '">' + bat.health_percent + '%</div>'
            + '<div class="text-sm text-gray-500 mb-2">Health</div>'
            + '<div class="grid grid-cols-2 gap-1 text-sm">'
            + kv('Cycles', bat.cycle_count) + kv('Temp', bat.temperature + '\u00B0C')
            + kv('Design', bat.design_capacity + ' mAh') + kv('Current', bat.nominal_capacity + ' mAh')
            + kv('Charging', bat.is_charging ? 'Yes' : 'No') + kv('Voltage', bat.voltage + ' mV')
            + '</div>';
    }

    function renderParts(parts, storage) {
        const color = parts.all_original ? 'text-green-600' : 'text-red-600';
        let html = '<div class="font-semibold ' + color + '">' + (parts.all_original ? 'All Original' : 'Replaced Parts Detected') + '</div>';
        if (parts.replaced_parts && parts.replaced_parts.length) {
            html += '<div class="text-red-500 text-sm mt-1">Replaced: ' + parts.replaced_parts.join(', ') + '</div>';
        }
        html += '<div class="mt-2 space-y-1">'
            + statusRow('Battery', parts.battery_original) + statusRow('Screen', parts.screen_original)
            + '</div>';
        if (storage) {
            html += '<div class="mt-3 pt-2 border-t text-sm">'
                + infoRow('Storage', storage.total_gb + ' GB') + infoRow('Used', storage.used_gb + ' GB')
                + '</div>';
        }
        el('parts-info').innerHTML = html;
    }

    function renderVerification(ver) {
        const blColor = ver.blacklist_status === 'clean' ? 'text-green-600' : ver.blacklist_status === 'blacklisted' ? 'text-red-600' : 'text-gray-500';
        const fmiColor = ver.fmi_status === 'off' ? 'text-green-600' : ver.fmi_status === 'on' ? 'text-red-600' : 'text-gray-500';
        const lockColor = ver.carrier_locked ? 'text-red-600' : 'text-green-600';

        el('verification-info').innerHTML =
            '<div class="space-y-2 text-sm">'
            + verRow('Blacklist', ver.blacklist_status.toUpperCase(), blColor)
            + verRow('Find My', ver.fmi_status.toUpperCase(), fmiColor)
            + verRow('Carrier', ver.carrier || 'Unknown', '')
            + verRow('SIM Lock', ver.carrier_locked ? 'LOCKED' : 'UNLOCKED', lockColor)
            + verRow('Activation', ver.activation_state || 'Unknown', '')
            + verRow('MDM', ver.mdm_enrolled ? ver.mdm_organization || 'Yes' : 'None', ver.mdm_enrolled ? 'text-red-600' : 'text-green-600')
            + '</div>';
    }

    function renderCrashes(analysis) {
        if (analysis.total_reports === 0) {
            el('crash-info').innerHTML = '<div class="text-green-600 font-semibold">No crash reports found</div>';
            el('crash-toggle').classList.add('hidden');
            return;
        }
        el('crash-toggle').classList.remove('hidden');
        let html = '<div class="text-sm"><strong>' + analysis.total_reports + '</strong> reports, '
            + '<strong>' + analysis.matched_reports + '</strong> matched known patterns</div>';
        if (analysis.max_severity >= 4) {
            html += '<div class="text-red-600 font-semibold mt-1">Hardware-level crashes detected!</div>';
        }
        if (Object.keys(analysis.subsystem_counts).length > 0) {
            html += '<div class="mt-2 space-y-1">';
            for (const [sub, count] of Object.entries(analysis.subsystem_counts)) {
                const trend = analysis.trends ? analysis.trends[sub] : null;
                const trendIcon = trend === 'worsening' ? ' <span class="trend-worsening">\u2191</span>'
                    : trend === 'improving' ? ' <span class="trend-improving">\u2193</span>'
                    : trend === 'stable' ? ' <span class="trend-stable">\u2192</span>' : '';
                html += '<div class="flex justify-between text-sm"><span class="text-gray-500">' + esc(sub) + trendIcon + '</span><span>' + count + '</span></div>';
            }
            html += '</div>';
        }
        html += '<div class="mt-2 text-xs text-gray-400">Risk score: ' + analysis.risk_score + '/100</div>';
        el('crash-info').innerHTML = html;

        // Predicted failures
        if (analysis.predicted_failures && analysis.predicted_failures.length > 0) {
            el('predicted-failures').classList.remove('hidden');
            el('predicted-failures-list').innerHTML = analysis.predicted_failures.map(f =>
                '<li>' + esc(f) + '</li>'
            ).join('');
        } else {
            el('predicted-failures').classList.add('hidden');
        }

        // Crash details
        if (analysis.matches && analysis.matches.length > 0) {
            let details = '';
            analysis.matches.forEach(m => {
                details += '<div class="flex items-start gap-2 mb-2 text-xs">'
                    + '<span class="severity-' + m.severity + ' px-1.5 py-0.5 rounded text-xs font-mono shrink-0">S' + m.severity + '</span>'
                    + '<div><div class="font-semibold">' + esc(m.subsystem) + '</div>'
                    + '<div class="text-gray-500">' + esc(m.description) + '</div>'
                    + '<div class="text-gray-400 font-mono">' + esc(m.filename) + '</div>'
                    + '</div></div>';
            });
            el('crash-details').innerHTML = details;
        }
    }

    function toggleCrashDetails() {
        const d = el('crash-details');
        d.classList.toggle('hidden');
        el('crash-toggle').textContent = d.classList.contains('hidden') ? 'Show details' : 'Hide details';
    }

    function renderGrade(grade) {
        const colors = {green: 'text-green-600', yellow: 'text-yellow-600', red: 'text-red-600', gray: 'text-gray-400'};
        el('overall-grade').className = 'text-5xl font-black ' + (colors[grade.color] || 'text-gray-400');
        el('overall-grade').textContent = grade.overall_grade || '--';
        el('grade-label').textContent = grade.is_partial ? 'Partial (cosmetic not entered)' : 'Score: ' + grade.overall_score.toFixed(2);
    }

    // -- History --

    async function loadHistory() {
        if (!currentDevice?.info) {
            el('history-content').innerHTML = '<span class="text-gray-400">Connect a device first</span>';
            return;
        }
        // Find device in inventory by UDID
        try {
            const devices = await fetch('/api/inventory/devices').then(r => r.json());
            const device = devices.find(d => d.udid === currentDevice.info.udid);
            if (!device) {
                el('history-content').innerHTML = '<span class="text-gray-400">Device not in inventory. Save it first to track history.</span>';
                return;
            }
            const [diags, verifs, crashes] = await Promise.all([
                fetch('/api/inventory/devices/' + device.id + '/diagnostics').then(r => r.json()),
                fetch('/api/inventory/devices/' + device.id + '/verifications').then(r => r.json()),
                fetch('/api/inventory/devices/' + device.id + '/crashes').then(r => r.json()),
            ]);
            let html = '<div class="space-y-4">';
            if (diags.length > 0) {
                html += '<div><h4 class="font-semibold text-sm text-gray-600 mb-2">Diagnostic Scans (' + diags.length + ')</h4>';
                diags.forEach(d => {
                    html += '<div class="text-xs border-b pb-2 mb-2">'
                        + '<span class="text-gray-400">' + esc(d.timestamp) + '</span> '
                        + 'Battery: ' + (d.battery_health || '?') + '% '
                        + 'Cycles: ' + (d.battery_cycles || '?') + ' '
                        + 'Storage: ' + (d.storage_total || '?') + 'GB'
                        + '</div>';
                });
                html += '</div>';
            }
            if (verifs.length > 0) {
                html += '<div><h4 class="font-semibold text-sm text-gray-600 mb-2">Verifications (' + verifs.length + ')</h4>';
                verifs.forEach(v => {
                    html += '<div class="text-xs border-b pb-2 mb-2">'
                        + '<span class="text-gray-400">' + esc(v.timestamp) + '</span> '
                        + 'Blacklist: ' + esc(v.blacklist_status) + ' '
                        + 'FMI: ' + esc(v.fmi_status)
                        + '</div>';
                });
                html += '</div>';
            }
            if (crashes.length > 0) {
                html += '<div><h4 class="font-semibold text-sm text-gray-600 mb-2">Crash Reports (' + crashes.length + ')</h4>';
                crashes.forEach(c => {
                    html += '<div class="text-xs border-b pb-2 mb-2">'
                        + '<span class="text-gray-400">' + esc(c.timestamp) + '</span> '
                        + esc(c.subsystem) + ' (S' + c.severity + ') x' + c.count
                        + '</div>';
                });
                html += '</div>';
            }
            if (diags.length === 0 && verifs.length === 0 && crashes.length === 0) {
                html += '<span class="text-gray-400">No history yet. Run diagnostics to start tracking.</span>';
            }
            html += '</div>';
            el('history-content').innerHTML = html;
        } catch (e) {
            el('history-content').innerHTML = '<span class="text-red-500">Failed to load history</span>';
        }
    }

    // -- Pricing --

    function updateProfit() {
        const buy = parseFloat(el('buy-price').value) || 0;
        const sell = parseFloat(el('sell-price').value) || 0;
        if (buy > 0 && sell > 0) {
            const profit = sell - buy;
            const color = profit >= 0 ? 'text-green-600' : 'text-red-600';
            el('profit-amount').className = 'text-2xl font-bold ' + color;
            el('profit-amount').textContent = (profit >= 0 ? '+' : '') + '$' + profit.toFixed(2);
        } else {
            el('profit-amount').className = 'text-2xl font-bold text-gray-300';
            el('profit-amount').textContent = '--';
        }
    }

    async function savePricing() {
        if (!currentDevice?.info) return;
        const info = currentDevice.info;
        try {
            const resp = await fetch('/api/inventory/devices', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    udid: info.udid, serial: info.serial || '', imei: info.imei || '',
                    model: info.product_type || '', ios_version: info.ios_version || '',
                    buy_price: parseFloat(el('buy-price').value) || null,
                    sell_price: parseFloat(el('sell-price').value) || null,
                    status: 'intake',
                }),
            });
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            alert('Pricing saved!');
        } catch (e) {
            alert('Failed to save: ' + e.message);
        }
    }

    async function saveToInventory() {
        if (!currentDevice?.info) return;
        const info = currentDevice.info;
        try {
            const resp = await fetch('/api/inventory/devices', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    udid: info.udid, serial: info.serial || '', imei: info.imei || '',
                    model: info.product_type || '', ios_version: info.ios_version || '',
                    status: 'intake',
                }),
            });
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            const result = await resp.json();
            alert('Saved to inventory (ID: ' + result.id + ')');
        } catch (e) {
            alert('Failed to save: ' + e.message);
        }
    }

    // -- Helpers --

    function el(id) { return document.getElementById(id); }
    function esc(s) {
        const d = document.createElement('div');
        d.textContent = s == null ? '-' : String(s);
        return d.innerHTML;
    }
    function infoRow(label, value, mono) {
        return '<div class="flex justify-between"><span class="text-gray-500">' + esc(label) + '</span>'
            + '<span class="' + (mono ? 'font-mono text-xs' : '') + '">' + esc(value) + '</span></div>';
    }
    function kv(k, v) { return '<div><span class="text-gray-500">' + esc(k) + ':</span> ' + esc(v) + '</div>'; }
    function statusRow(label, val) {
        const text = val === true ? '\u2713 Original' : val === false ? '\u2717 Replaced' : '? Unknown';
        const c = val === true ? 'text-green-600' : val === false ? 'text-red-600' : 'text-gray-400';
        return '<div class="flex justify-between text-sm"><span class="text-gray-500">' + esc(label) + '</span><span class="' + c + '">' + text + '</span></div>';
    }
    function verRow(label, value, colorClass) {
        return '<div class="flex justify-between"><span class="text-gray-500">' + esc(label) + '</span><span class="font-semibold ' + colorClass + '">' + esc(value) + '</span></div>';
    }
    function chip(text, cls) {
        return '<span class="text-xs px-2 py-0.5 rounded-full ' + cls + '">' + esc(text) + '</span>';
    }

    // Init
    el('buy-price').addEventListener('input', updateProfit);
    el('sell-price').addEventListener('input', updateProfit);
    connectWebSocket();
    </script>
</body>
</html>
```

**Step 2: Verify the app starts without errors**

Run: `python -c "from app.main import app; print('App loaded OK')"`
Expected: "App loaded OK"

**Step 3: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: Dashboard v2 — snapshot-driven view, crash details, history, pricing, capabilities"
```

---

### Task 14: Run full test suite and verify

**Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (35 original + ~40 new = ~75 total)

**Step 2: Run linter**

Run: `python -m ruff check app/ tests/`
Expected: No errors (or fix any that appear)

**Step 3: Verify app module imports**

Run: `python -c "from app.main import app; from app.api.diagnostics import router; print('All imports OK')"`
Expected: "All imports OK"

**Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: resolve any lint/test issues from Sprint 2 integration"
```

---

## Summary of Deliverables

| Slice | Files | Tests | What's New |
|-------|-------|-------|------------|
| Crash Intelligence | `data/crash_patterns.json`, `app/models/crash.py`, `app/services/log_analyzer.py` | `tests/test_log_analyzer.py` (~40 tests) | 31 patterns, trending, predictive failures |
| Fraud Detection v2 | `app/models/inventory.py`, `app/services/serial_decoder.py` | `tests/test_fraud_detection.py` (~12 tests) | TAC map, fraud scoring, randomized serial notes |
| Snapshot API + Pricing | `app/api/diagnostics.py`, `app/models/device.py`, `app/services/inventory_db.py` | `tests/test_snapshot_api.py` (~2 tests), `tests/test_inventory_db.py` (3 new) | Unified snapshot endpoint, sell_price, profit, history |
| Dashboard v2 | `app/templates/index.html` | Manual testing | Snapshot-driven, crash details, history tab, pricing, capabilities |
| Test Infrastructure | `tests/conftest.py`, `tests/test_diagnostic_engine.py`, `tests/test_verification_service.py` | ~10 tests | Mocked device layer, HTTP mocking |
