"""Tests for crash log analyzer — pattern matching, trending, and predictions."""

import json
from pathlib import Path

import pytest

from app.models.crash import CrashAnalysis
from app.services.log_analyzer import analyze_crash_text

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
