"""Shared test fixtures — mock pymobiledevice3 and external services."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

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
        "Temperature": 2950,
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
