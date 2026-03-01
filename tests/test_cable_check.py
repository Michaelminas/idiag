"""Tests for check_cable_quality() in diagnostic_engine.py."""

from unittest.mock import MagicMock

import pytest

from app.services.diagnostic_engine import check_cable_quality


def _make_lockdown(battery_info=None, connection_speed=None, raise_exc=None):
    """Build a mock lockdown that returns different values per domain/key."""
    mock = MagicMock()

    def _get_value(domain=None, key=None):
        if raise_exc:
            raise raise_exc
        if domain == "com.apple.mobile.battery":
            return battery_info
        if key == "ConnectionSpeed":
            return connection_speed
        return None

    mock.get_value = MagicMock(side_effect=_get_value)
    return mock


class TestCableCheckUSB2Good:
    """USB 2.0 cable with charging — no warnings."""

    def test_usb2_good_cable(self):
        lockdown = _make_lockdown(
            battery_info={"ExternalChargeCapable": True},
            connection_speed=480_000_000,
        )
        result = check_cable_quality(lockdown)

        assert result.connection_type == "USB 2.0 High-Speed"
        assert result.charge_capable is True
        assert result.data_capable is True
        assert result.negotiated_speed == "480 Mbps"
        assert result.warnings == []


class TestCableCheckNoCharge:
    """Cable that cannot charge — warning emitted."""

    def test_no_charge_capability(self):
        lockdown = _make_lockdown(
            battery_info={"ExternalChargeCapable": False},
            connection_speed=480_000_000,
        )
        result = check_cable_quality(lockdown)

        assert result.charge_capable is False
        assert any("charging" in w.lower() for w in result.warnings)


class TestCableCheckLowSpeed:
    """USB 1.1 full-speed — warning about low speed."""

    def test_low_speed_cable(self):
        lockdown = _make_lockdown(
            battery_info={"ExternalChargeCapable": True},
            connection_speed=12_000_000,
        )
        result = check_cable_quality(lockdown)

        assert result.connection_type == "USB 1.1 Full-Speed (slow)"
        assert result.negotiated_speed == "12 Mbps"
        assert any("low" in w.lower() for w in result.warnings)


class TestCableCheckMissingProperties:
    """get_value returns None for everything — graceful defaults."""

    def test_missing_properties(self):
        lockdown = _make_lockdown(battery_info=None, connection_speed=None)
        result = check_cable_quality(lockdown)

        assert result.connection_type == "Unknown"
        assert result.data_capable is True
        assert result.negotiated_speed is None


class TestCableCheckException:
    """get_value raises — warnings list populated, no crash."""

    def test_exception_handling(self):
        lockdown = _make_lockdown(raise_exc=OSError("USB disconnected"))
        result = check_cable_quality(lockdown)

        assert len(result.warnings) > 0
        assert any("cable properties" in w.lower() or "usb disconnected" in w.lower() for w in result.warnings)
        assert result.data_capable is True
