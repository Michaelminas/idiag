"""Tests for crash log analyzer — pattern matching, trending, and predictions."""

import json
from pathlib import Path

import pytest

from app.models.crash import CrashAnalysis
from app.services.log_analyzer import (
    analyze_crash_text,
    compute_predicted_failures,
    compute_trends,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PATTERNS_PATH = Path(__file__).resolve().parent.parent / "data" / "crash_patterns.json"


def _load_pattern_list() -> list[dict]:
    with open(PATTERNS_PATH) as f:
        return json.load(f)


PATTERN_LIST = _load_pattern_list()


# ---------------------------------------------------------------------------
# Test fixtures file loading
# ---------------------------------------------------------------------------


class TestFixtureFiles:
    """Verify sample crash fixture files can be read and matched."""

    def test_camera_crash_fixture(self):
        text = (FIXTURES_DIR / "sample_camera_crash.ips").read_text()
        match = analyze_crash_text(text, "sample_camera_crash.ips")
        assert match is not None
        assert match.subsystem == "Camera"
        assert match.severity == 5

    def test_battery_crash_fixture(self):
        text = (FIXTURES_DIR / "sample_battery_crash.ips").read_text()
        match = analyze_crash_text(text, "sample_battery_crash.ips")
        assert match is not None
        assert match.subsystem == "Battery/Power"
        assert match.severity == 5

    def test_bluetooth_crash_fixture(self):
        text = (FIXTURES_DIR / "sample_bluetooth_crash.ips").read_text()
        match = analyze_crash_text(text, "sample_bluetooth_crash.ips")
        assert match is not None
        assert match.subsystem == "Bluetooth"
        assert match.severity == 3

    def test_faceid_crash_fixture(self):
        text = (FIXTURES_DIR / "sample_faceid_crash.ips").read_text()
        match = analyze_crash_text(text, "sample_faceid_crash.ips")
        assert match is not None
        assert match.subsystem == "Face ID"
        assert match.severity == 5

    def test_no_match_fixture(self):
        text = (FIXTURES_DIR / "sample_no_match.ips").read_text()
        match = analyze_crash_text(text, "sample_no_match.ips")
        assert match is None


# ---------------------------------------------------------------------------
# All 31 patterns — individual match tests
# ---------------------------------------------------------------------------


class TestAllPatterns:
    """Verify each of the 31 crash patterns matches correctly."""

    def test_pattern_count(self):
        assert len(PATTERN_LIST) == 31

    # 1. Camera
    def test_camera_pattern(self):
        m = analyze_crash_text("kernel panic in AppleH13CamISP at 0xfff")
        assert m is not None and m.subsystem == "Camera" and m.severity == 5

    # 2. WiFi
    def test_wifi_pattern(self):
        m = analyze_crash_text("kernel panic in AppleBCMWLAN driver reset")
        assert m is not None and m.subsystem == "WiFi" and m.severity == 4

    # 3. Display
    def test_display_pattern(self):
        m = analyze_crash_text("EXC_RESOURCE cpu limit exceeded backboardd")
        assert m is not None and m.subsystem == "Display" and m.severity == 3

    # 4. Battery/Power
    def test_battery_power_pattern(self):
        m = analyze_crash_text("kernel panic in AppleARMPMU failure")
        assert m is not None and m.subsystem == "Battery/Power" and m.severity == 5

    # 5. Baseband
    def test_baseband_pattern(self):
        m = analyze_crash_text("watchdog timeout in CommCenter modem hang")
        assert m is not None and m.subsystem == "Baseband" and m.severity == 4

    # 6. Security
    def test_security_pattern(self):
        m = analyze_crash_text("kernel panic in AppleSEP secure enclave")
        assert m is not None and m.subsystem == "Security" and m.severity == 5

    # 7. GPU
    def test_gpu_pattern(self):
        m = analyze_crash_text("EXC_BAD_ACCESS in AGXMetal shader crash")
        assert m is not None and m.subsystem == "GPU" and m.severity == 3

    # 8. Storage
    def test_storage_pattern(self):
        m = analyze_crash_text("kernel panic in IONVMe controller error")
        assert m is not None and m.subsystem == "Storage" and m.severity == 5

    # 9. System
    def test_system_pattern(self):
        m = analyze_crash_text("repeated springboardd crashes detected")
        assert m is not None and m.subsystem == "System" and m.severity == 2

    # 10. Thermal
    def test_thermal_pattern(self):
        m = analyze_crash_text("thermalmonitord EXC_RESOURCE threshold exceeded")
        assert m is not None and m.subsystem == "Thermal" and m.severity == 4

    # 11. Audio
    def test_audio_pattern(self):
        m = analyze_crash_text("kernel panic in AppleAudioCodecs codec fail")
        assert m is not None and m.subsystem == "Audio" and m.severity == 4

    # 12. Bluetooth
    def test_bluetooth_pattern(self):
        m = analyze_crash_text("kernel panic in AppleBCMBTFW firmware error")
        assert m is not None and m.subsystem == "Bluetooth" and m.severity == 3

    # 13. NFC
    def test_nfc_pattern(self):
        m = analyze_crash_text("kernel panic in AppleNFC controller failure")
        assert m is not None and m.subsystem == "NFC" and m.severity == 3

    # 14. Accelerometer
    def test_accelerometer_pattern(self):
        m = analyze_crash_text("EXC_BAD_ACCESS in CoreMotion sensor crash")
        assert m is not None and m.subsystem == "Accelerometer" and m.severity == 3

    # 15. Gyroscope
    def test_gyroscope_pattern(self):
        m = analyze_crash_text("kernel panic in AppleARMGyro sensor failure")
        assert m is not None and m.subsystem == "Gyroscope" and m.severity == 3

    # 16. Face ID
    def test_faceid_pattern(self):
        m = analyze_crash_text("kernel panic in BiometricKit pearl calibration")
        assert m is not None and m.subsystem == "Face ID" and m.severity == 5

    # 17. Touch ID
    def test_touchid_pattern(self):
        m = analyze_crash_text("kernel panic in AppleMesa sensor failure")
        assert m is not None and m.subsystem == "Touch ID" and m.severity == 5

    # 18. Proximity
    def test_proximity_pattern(self):
        m = analyze_crash_text("EXC_BAD_ACCESS in AppleProximity sensor issue")
        assert m is not None and m.subsystem == "Proximity" and m.severity == 2

    # 19. LiDAR
    def test_lidar_pattern(self):
        m = analyze_crash_text("kernel panic in AppleLiDAR scanner failure")
        assert m is not None and m.subsystem == "LiDAR" and m.severity == 3

    # 20. Taptic
    def test_taptic_pattern(self):
        m = analyze_crash_text("kernel panic in AppleHaptics engine failure")
        assert m is not None and m.subsystem == "Taptic" and m.severity == 3

    # 21. Charging
    def test_charging_pattern(self):
        m = analyze_crash_text("kernel panic in AppleUSBPD controller failure")
        assert m is not None and m.subsystem == "Charging" and m.severity == 4

    # 22. USB
    def test_usb_pattern(self):
        m = analyze_crash_text("kernel panic in IOUSBDeviceFamily error")
        assert m is not None and m.subsystem == "USB" and m.severity == 3

    # 23. Compass
    def test_compass_pattern(self):
        m = analyze_crash_text("EXC_BAD_ACCESS in AppleARMCompass sensor issue")
        assert m is not None and m.subsystem == "Compass" and m.severity == 2

    # 24. Ambient Light
    def test_ambient_light_pattern(self):
        m = analyze_crash_text("kernel panic in AppleALS sensor failure")
        assert m is not None and m.subsystem == "Ambient Light" and m.severity == 2

    # 25. Barometer
    def test_barometer_pattern(self):
        m = analyze_crash_text("EXC_BAD_ACCESS in AppleBarometer altitude issue")
        assert m is not None and m.subsystem == "Barometer" and m.severity == 2

    # 26. UWB
    def test_uwb_pattern(self):
        m = analyze_crash_text("kernel panic in AppleUWB chip failure")
        assert m is not None and m.subsystem == "UWB" and m.severity == 3

    # 27. Neural Engine
    def test_neural_engine_pattern(self):
        m = analyze_crash_text("kernel panic in ANE compute failure")
        assert m is not None and m.subsystem == "Neural Engine" and m.severity == 4

    # 28. Memory
    def test_memory_pattern(self):
        m = analyze_crash_text("EXC_RESOURCE memory limit jetsam killed")
        assert m is not None and m.subsystem == "Memory" and m.severity == 3

    # 29. Sleep/Wake
    def test_sleep_wake_pattern(self):
        m = analyze_crash_text("kernel panic in SleepServices wake failure")
        assert m is not None and m.subsystem == "Sleep/Wake" and m.severity == 4

    # 30. SIM
    def test_sim_pattern(self):
        m = analyze_crash_text("watchdog timeout in coreTelephony stack hang")
        assert m is not None and m.subsystem == "SIM" and m.severity == 3

    # 31. Recovery
    def test_recovery_pattern(self):
        m = analyze_crash_text("repeated iBoot failures restore loop detected")
        assert m is not None and m.subsystem == "Recovery" and m.severity == 5

    # No match
    def test_no_match_returns_none(self):
        m = analyze_crash_text("nothing interesting here at all")
        assert m is None

    def test_empty_text_returns_none(self):
        m = analyze_crash_text("")
        assert m is None

    # Case insensitivity
    def test_case_insensitive(self):
        m = analyze_crash_text("KERNEL PANIC IN APPLEBCMWLAN driver")
        assert m is not None and m.subsystem == "WiFi"


# ---------------------------------------------------------------------------
# CrashAnalysis model fields
# ---------------------------------------------------------------------------


class TestCrashAnalysisModelFields:
    """Verify trends and predicted_failures fields exist on CrashAnalysis."""

    def test_trends_field_default(self):
        analysis = CrashAnalysis()
        assert analysis.trends == {}

    def test_predicted_failures_field_default(self):
        analysis = CrashAnalysis()
        assert analysis.predicted_failures == []

    def test_trends_field_accepts_data(self):
        analysis = CrashAnalysis(
            trends={"Camera": "worsening", "WiFi": "stable"}
        )
        assert analysis.trends["Camera"] == "worsening"
        assert analysis.trends["WiFi"] == "stable"

    def test_predicted_failures_field_accepts_data(self):
        analysis = CrashAnalysis(
            predicted_failures=["Camera hardware — 5 crashes, increasing trend."]
        )
        assert len(analysis.predicted_failures) == 1
        assert "Camera" in analysis.predicted_failures[0]


# ---------------------------------------------------------------------------
# compute_trends tests
# ---------------------------------------------------------------------------


class TestComputeTrends:
    """Tests for compute_trends() function."""

    def test_no_history_returns_empty(self):
        result = compute_trends({"Camera": 5}, [])
        assert result == {}

    def test_stable_counts(self):
        current = {"Camera": 3, "WiFi": 2}
        history = [{"Camera": 3, "WiFi": 2}]
        result = compute_trends(current, history)
        assert result["Camera"] == "stable"
        assert result["WiFi"] == "stable"

    def test_worsening_counts(self):
        current = {"Camera": 5}
        history = [{"Camera": 3}]
        result = compute_trends(current, history)
        assert result["Camera"] == "worsening"

    def test_improving_counts(self):
        current = {"Camera": 1}
        history = [{"Camera": 5}]
        result = compute_trends(current, history)
        assert result["Camera"] == "improving"

    def test_new_subsystem_not_in_history_skipped(self):
        current = {"Camera": 3, "NFC": 1}
        history = [{"Camera": 3}]
        result = compute_trends(current, history)
        assert result["Camera"] == "stable"
        assert "NFC" not in result

    def test_multiple_history_uses_most_recent(self):
        current = {"Camera": 5}
        history = [
            {"Camera": 10},  # older
            {"Camera": 3},   # most recent
        ]
        result = compute_trends(current, history)
        assert result["Camera"] == "worsening"

    def test_mixed_trends(self):
        current = {"Camera": 5, "WiFi": 2, "GPU": 3}
        history = [{"Camera": 3, "WiFi": 4, "GPU": 3}]
        result = compute_trends(current, history)
        assert result["Camera"] == "worsening"
        assert result["WiFi"] == "improving"
        assert result["GPU"] == "stable"


# ---------------------------------------------------------------------------
# compute_predicted_failures tests
# ---------------------------------------------------------------------------


class TestComputePredictedFailures:
    """Tests for compute_predicted_failures() function."""

    def test_worsening_high_severity_produces_failure(self):
        trends = {"Camera": "worsening"}
        counts = {"Camera": 5}
        severity_map = {"Camera": 5}
        result = compute_predicted_failures(trends, counts, severity_map)
        assert len(result) == 1
        assert "Camera" in result[0]
        assert "5 crashes" in result[0]
        assert "increasing trend" in result[0]

    def test_stable_high_severity_no_failure(self):
        trends = {"Camera": "stable"}
        counts = {"Camera": 5}
        severity_map = {"Camera": 5}
        result = compute_predicted_failures(trends, counts, severity_map)
        assert result == []

    def test_improving_high_severity_no_failure(self):
        trends = {"Camera": "improving"}
        counts = {"Camera": 2}
        severity_map = {"Camera": 5}
        result = compute_predicted_failures(trends, counts, severity_map)
        assert result == []

    def test_worsening_low_severity_no_failure(self):
        trends = {"GPU": "worsening"}
        counts = {"GPU": 3}
        severity_map = {"GPU": 3}
        result = compute_predicted_failures(trends, counts, severity_map)
        assert result == []

    def test_worsening_severity_4_produces_failure(self):
        trends = {"Thermal": "worsening"}
        counts = {"Thermal": 4}
        severity_map = {"Thermal": 4}
        result = compute_predicted_failures(trends, counts, severity_map)
        assert len(result) == 1
        assert "Thermal" in result[0]

    def test_multiple_worsening_subsystems(self):
        trends = {"Camera": "worsening", "Storage": "worsening", "GPU": "worsening"}
        counts = {"Camera": 5, "Storage": 3, "GPU": 2}
        severity_map = {"Camera": 5, "Storage": 5, "GPU": 3}
        result = compute_predicted_failures(trends, counts, severity_map)
        # GPU has severity 3, so only Camera and Storage
        assert len(result) == 2
        subsystems = " ".join(result)
        assert "Camera" in subsystems
        assert "Storage" in subsystems
        assert "GPU" not in subsystems

    def test_empty_trends_no_failures(self):
        result = compute_predicted_failures({}, {}, {})
        assert result == []

    def test_subsystem_missing_from_severity_map(self):
        trends = {"Unknown": "worsening"}
        counts = {"Unknown": 3}
        severity_map = {}  # unknown not in map
        result = compute_predicted_failures(trends, counts, severity_map)
        assert result == []  # severity defaults to 0, below threshold
