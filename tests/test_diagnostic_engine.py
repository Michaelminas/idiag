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
    def _make_mock_diag_service(self, battery_data=None, gestalt_data=None):
        mock = MagicMock()
        mock.get_battery.return_value = battery_data or {}
        mock.mobilegestalt.return_value = gestalt_data or {"MobileGestalt": {}}
        mock.__enter__ = MagicMock(return_value=mock)
        mock.__exit__ = MagicMock(return_value=False)
        return mock

    @patch("pymobiledevice3.services.diagnostics.DiagnosticsService")
    @patch("pymobiledevice3.lockdown.create_using_usbmux")
    def test_returns_battery_info(
        self, mock_create, mock_diag_cls, mock_lockdown, mock_battery_data
    ):
        mock_create.return_value.__enter__ = MagicMock(return_value=mock_lockdown)
        mock_create.return_value.__exit__ = MagicMock(return_value=False)
        mock_diag = self._make_mock_diag_service(
            battery_data=mock_battery_data,
            gestalt_data={
                "MobileGestalt": {"BatteryIsOriginal": True, "a/ScreenIsOriginal": True}
            },
        )
        mock_diag_cls.return_value = mock_diag

        result = run_diagnostics("test-udid")

        assert result.battery.health_percent == pytest.approx(95.9, rel=0.1)
        assert result.battery.cycle_count == 247
        assert result.battery.temperature == 29.5

    @patch("pymobiledevice3.services.diagnostics.DiagnosticsService")
    @patch("pymobiledevice3.lockdown.create_using_usbmux")
    def test_returns_storage_info(self, mock_create, mock_diag_cls, mock_lockdown):
        mock_create.return_value.__enter__ = MagicMock(return_value=mock_lockdown)
        mock_create.return_value.__exit__ = MagicMock(return_value=False)
        mock_diag = self._make_mock_diag_service()
        mock_diag_cls.return_value = mock_diag

        result = run_diagnostics("test-udid")

        assert result.storage.total_gb == 128.0
        assert result.storage.available_gb == 64.0

    @patch("pymobiledevice3.services.diagnostics.DiagnosticsService")
    @patch("pymobiledevice3.lockdown.create_using_usbmux")
    def test_replaced_parts_detected(self, mock_create, mock_diag_cls, mock_lockdown):
        mock_create.return_value.__enter__ = MagicMock(return_value=mock_lockdown)
        mock_create.return_value.__exit__ = MagicMock(return_value=False)
        mock_diag = self._make_mock_diag_service(
            gestalt_data={
                "MobileGestalt": {"BatteryIsOriginal": False, "a/ScreenIsOriginal": True}
            },
        )
        mock_diag_cls.return_value = mock_diag

        result = run_diagnostics("test-udid")

        assert not result.parts.all_original
        assert "battery" in result.parts.replaced_parts
