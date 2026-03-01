"""Tests for the tools API router — bypass tools, futurerestore, cable check."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.tools import BypassResult, CableCheckResult, RestoreCompatibility

client = TestClient(app)


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


class TestToolsAvailability:
    @patch("app.api.tools.futurerestore.check_futurerestore_available", return_value=True)
    @patch("app.api.tools.bypass_tools.check_ssh_ramdisk_available", return_value=True)
    @patch("app.api.tools.bypass_tools.check_broque_available", return_value=False)
    @patch("app.api.tools.bypass_tools.check_checkra1n_available", return_value=True)
    def test_availability_returns_all_tools(
        self, mock_checkra1n, mock_broque, mock_ssh, mock_fr
    ):
        resp = client.get("/api/tools/availability")
        assert resp.status_code == 200
        data = resp.json()
        assert data["checkra1n"] is True
        assert data["broque"] is False
        assert data["ssh_ramdisk"] is True
        assert data["futurerestore"] is True

    @patch("app.api.tools.futurerestore.check_futurerestore_available", return_value=False)
    @patch("app.api.tools.bypass_tools.check_ssh_ramdisk_available", return_value=False)
    @patch("app.api.tools.bypass_tools.check_broque_available", return_value=False)
    @patch("app.api.tools.bypass_tools.check_checkra1n_available", return_value=False)
    def test_availability_all_unavailable(
        self, mock_checkra1n, mock_broque, mock_ssh, mock_fr
    ):
        resp = client.get("/api/tools/availability")
        assert resp.status_code == 200
        data = resp.json()
        assert all(v is False for v in data.values())


# ---------------------------------------------------------------------------
# checkra1n
# ---------------------------------------------------------------------------


class TestCheckra1nEndpoint:
    @patch("app.api.tools.bypass_tools.run_checkra1n")
    def test_checkra1n_success(self, mock_run):
        mock_run.return_value = BypassResult(
            success=True,
            tool="checkra1n",
            message="Jailbreak complete",
            timestamp=datetime(2025, 1, 1),
        )
        resp = client.post("/api/tools/checkra1n/test-udid")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["tool"] == "checkra1n"
        assert data["message"] == "Jailbreak complete"
        mock_run.assert_called_once_with("test-udid")

    @patch("app.api.tools.bypass_tools.run_checkra1n")
    def test_checkra1n_failure(self, mock_run):
        mock_run.return_value = BypassResult(
            success=False,
            tool="checkra1n",
            error="not_available",
            message="checkra1n is not installed",
            timestamp=datetime(2025, 1, 1),
        )
        resp = client.post("/api/tools/checkra1n/test-udid")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["error"] == "not_available"


# ---------------------------------------------------------------------------
# Broque Ramdisk
# ---------------------------------------------------------------------------


class TestBroqueEndpoint:
    @patch("app.api.tools.bypass_tools.run_broque_bypass")
    def test_broque_success(self, mock_run):
        mock_run.return_value = BypassResult(
            success=True,
            tool="broque",
            message="Bypass complete",
            timestamp=datetime(2025, 1, 1),
        )
        resp = client.post("/api/tools/broque/test-udid")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["tool"] == "broque"
        mock_run.assert_called_once_with("test-udid")

    @patch("app.api.tools.bypass_tools.run_broque_bypass")
    def test_broque_failure(self, mock_run):
        mock_run.return_value = BypassResult(
            success=False,
            tool="broque",
            error="not_available",
            message="Broque Ramdisk tools not found",
            timestamp=datetime(2025, 1, 1),
        )
        resp = client.post("/api/tools/broque/test-udid")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["error"] == "not_available"


# ---------------------------------------------------------------------------
# SSH Ramdisk
# ---------------------------------------------------------------------------


class TestSSHRamdiskEndpoint:
    @patch("app.api.tools.bypass_tools.boot_ssh_ramdisk")
    def test_boot_ssh_ramdisk_success(self, mock_boot):
        mock_boot.return_value = BypassResult(
            success=True,
            tool="ssh_ramdisk",
            message="SSH Ramdisk booted",
            timestamp=datetime(2025, 1, 1),
        )
        resp = client.post("/api/tools/ssh-ramdisk/test-udid")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["tool"] == "ssh_ramdisk"
        mock_boot.assert_called_once_with("test-udid")

    @patch("app.api.tools.bypass_tools.boot_ssh_ramdisk")
    def test_boot_ssh_ramdisk_failure(self, mock_boot):
        mock_boot.return_value = BypassResult(
            success=False,
            tool="ssh_ramdisk",
            error="not_available",
            message="sshrd is not installed",
            timestamp=datetime(2025, 1, 1),
        )
        resp = client.post("/api/tools/ssh-ramdisk/test-udid")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False

    @patch("app.api.tools.bypass_tools.extract_data")
    def test_extract_data_success(self, mock_extract):
        mock_extract.return_value = {
            "photos": {"success": True, "message": "photos extracted successfully", "count": 42},
            "contacts": {"success": True, "message": "contacts extracted successfully", "count": 10},
        }
        resp = client.post(
            "/api/tools/ssh-ramdisk/test-udid/extract",
            json={"data_types": ["photos", "contacts"], "target_dir": "/tmp/extract"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["photos"]["success"] is True
        assert data["photos"]["count"] == 42
        assert data["contacts"]["success"] is True
        mock_extract.assert_called_once_with("test-udid", "/tmp/extract", ["photos", "contacts"])

    @patch("app.api.tools.bypass_tools.extract_data")
    def test_extract_data_unknown_type(self, mock_extract):
        mock_extract.return_value = {
            "unknown": {"success": False, "message": "Unknown data type: unknown", "count": 0},
        }
        resp = client.post(
            "/api/tools/ssh-ramdisk/test-udid/extract",
            json={"data_types": ["unknown"], "target_dir": "/tmp/extract"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["unknown"]["success"] is False


# ---------------------------------------------------------------------------
# FutureRestore
# ---------------------------------------------------------------------------


class TestFutureRestoreEndpoint:
    @patch("app.api.tools.futurerestore.check_compatibility")
    def test_check_compatibility(self, mock_check):
        mock_check.return_value = RestoreCompatibility(
            compatible=True,
            target_version="16.0",
            blob_valid=True,
            sep_compatible=True,
        )
        resp = client.get(
            "/api/tools/futurerestore/test-udid/check",
            params={"target_version": "16.0", "blob_path": "/tmp/blobs/test.shsh2"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["compatible"] is True
        assert data["target_version"] == "16.0"
        assert data["blob_valid"] is True

    @patch("app.api.tools.futurerestore.check_compatibility")
    def test_check_compatibility_fail(self, mock_check):
        mock_check.return_value = RestoreCompatibility(
            compatible=False,
            target_version="16.0",
            blob_valid=False,
            sep_compatible=False,
            reason="Blob file not found",
        )
        resp = client.get(
            "/api/tools/futurerestore/test-udid/check",
            params={"target_version": "16.0", "blob_path": "/tmp/nope.shsh2"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["compatible"] is False
        assert data["reason"] == "Blob file not found"

    @patch("app.api.tools.futurerestore.run_futurerestore")
    def test_run_futurerestore_success(self, mock_run):
        mock_run.return_value = BypassResult(
            success=True,
            tool="futurerestore",
            message="Restore complete",
            timestamp=datetime(2025, 1, 1),
        )
        resp = client.post(
            "/api/tools/futurerestore/test-udid",
            json={
                "ipsw_path": "/tmp/firmware.ipsw",
                "blob_path": "/tmp/blobs/test.shsh2",
                "set_nonce": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["tool"] == "futurerestore"

    @patch("app.api.tools.futurerestore.run_futurerestore")
    def test_run_futurerestore_default_set_nonce(self, mock_run):
        mock_run.return_value = BypassResult(
            success=True,
            tool="futurerestore",
            message="Restore complete",
            timestamp=datetime(2025, 1, 1),
        )
        resp = client.post(
            "/api/tools/futurerestore/test-udid",
            json={
                "ipsw_path": "/tmp/firmware.ipsw",
                "blob_path": "/tmp/blobs/test.shsh2",
            },
        )
        assert resp.status_code == 200
        # Verify set_nonce defaults to True
        call_args = mock_run.call_args
        assert call_args[0][3] is True  # set_nonce positional arg

    @patch("app.api.tools.futurerestore.run_futurerestore")
    def test_run_futurerestore_failure(self, mock_run):
        mock_run.return_value = BypassResult(
            success=False,
            tool="futurerestore",
            error="not_available",
            message="futurerestore is not installed",
            timestamp=datetime(2025, 1, 1),
        )
        resp = client.post(
            "/api/tools/futurerestore/test-udid",
            json={
                "ipsw_path": "/tmp/firmware.ipsw",
                "blob_path": "/tmp/blobs/test.shsh2",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["error"] == "not_available"


# ---------------------------------------------------------------------------
# Cable Check
# ---------------------------------------------------------------------------


class TestCableCheckEndpoint:
    @patch("app.api.tools.diagnostic_engine.check_cable_quality")
    @patch("app.api.tools.device_service.get_lockdown_client")
    def test_cable_check_success(self, mock_lockdown, mock_cable):
        mock_lock_ctx = MagicMock()
        mock_lock_obj = MagicMock()
        mock_lock_ctx.__enter__ = MagicMock(return_value=mock_lock_obj)
        mock_lock_ctx.__exit__ = MagicMock(return_value=False)
        mock_lockdown.return_value = mock_lock_ctx

        mock_cable.return_value = CableCheckResult(
            connection_type="USB 2.0 High-Speed",
            charge_capable=True,
            data_capable=True,
            negotiated_speed="480 Mbps",
            warnings=[],
        )
        resp = client.get("/api/tools/cable/test-udid")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connection_type"] == "USB 2.0 High-Speed"
        assert data["charge_capable"] is True
        assert data["data_capable"] is True
        assert data["negotiated_speed"] == "480 Mbps"
        assert data["warnings"] == []
        mock_cable.assert_called_once_with(mock_lock_obj)

    @patch("app.api.tools.diagnostic_engine.check_cable_quality")
    @patch("app.api.tools.device_service.get_lockdown_client")
    def test_cable_check_with_warnings(self, mock_lockdown, mock_cable):
        mock_lock_ctx = MagicMock()
        mock_lock_obj = MagicMock()
        mock_lock_ctx.__enter__ = MagicMock(return_value=mock_lock_obj)
        mock_lock_ctx.__exit__ = MagicMock(return_value=False)
        mock_lockdown.return_value = mock_lock_ctx

        mock_cable.return_value = CableCheckResult(
            connection_type="USB 1.1 Full-Speed (slow)",
            charge_capable=False,
            data_capable=True,
            negotiated_speed="12 Mbps",
            warnings=["Low USB speed detected", "Cable does not support charging"],
        )
        resp = client.get("/api/tools/cable/test-udid")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connection_type"] == "USB 1.1 Full-Speed (slow)"
        assert data["charge_capable"] is False
        assert len(data["warnings"]) == 2

    @patch("app.api.tools.device_service.get_lockdown_client")
    def test_cable_check_device_not_found(self, mock_lockdown):
        mock_lockdown.side_effect = Exception("Device not found")
        resp = client.get("/api/tools/cable/nonexistent")
        assert resp.status_code == 500
        data = resp.json()
        assert "detail" in data
