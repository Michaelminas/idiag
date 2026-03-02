"""Tests for app/services/bypass_tools.py — subprocess wrappers for bypass tools."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from app.models.tools import BypassResult


# ── TestCheckra1nAvailability ────────────────────────────────


class TestCheckra1nAvailability:
    @patch("app.services.bypass_tools.shutil.which", return_value="/usr/bin/checkra1n")
    def test_available(self, mock_which):
        with patch.object(sys.modules["app.services.bypass_tools"], "sys") as mock_sys:
            mock_sys.platform = "linux"
            from app.services.bypass_tools import check_checkra1n_available

            assert check_checkra1n_available() is True

    @patch("app.services.bypass_tools.shutil.which", return_value=None)
    def test_not_available(self, mock_which):
        with patch.object(sys.modules["app.services.bypass_tools"], "sys") as mock_sys:
            mock_sys.platform = "linux"
            from app.services.bypass_tools import check_checkra1n_available

            assert check_checkra1n_available() is False


# ── TestRunCheckra1n ─────────────────────────────────────────


class TestRunCheckra1n:
    @patch("app.services.bypass_tools.check_checkra1n_available", return_value=False)
    def test_not_available_returns_failure(self, mock_avail):
        from app.services.bypass_tools import run_checkra1n

        result = run_checkra1n("UDID123")
        assert result.success is False
        assert result.tool == "checkra1n"
        assert result.error == "not_available"

    @patch("app.services.bypass_tools.check_checkra1n_available", return_value=True)
    @patch("app.services.bypass_tools.subprocess.run")
    def test_success(self, mock_run, mock_avail):
        mock_run.return_value = MagicMock(returncode=0, stdout="Done", stderr="")

        from app.services.bypass_tools import run_checkra1n

        result = run_checkra1n("UDID123")
        assert result.success is True
        assert result.tool == "checkra1n"
        assert result.error is None
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "checkra1n" in cmd
        assert "-c" in cmd

    @patch("app.services.bypass_tools.check_checkra1n_available", return_value=True)
    @patch(
        "app.services.bypass_tools.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="checkra1n", timeout=600),
    )
    def test_timeout(self, mock_run, mock_avail):
        from app.services.bypass_tools import run_checkra1n

        result = run_checkra1n("UDID123")
        assert result.success is False
        assert result.tool == "checkra1n"
        assert result.error == "timeout"

    @patch("app.services.bypass_tools.check_checkra1n_available", return_value=True)
    @patch("app.services.bypass_tools.subprocess.run")
    def test_nonzero_exit(self, mock_run, mock_avail):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Error: device not in DFU"
        )

        from app.services.bypass_tools import run_checkra1n

        result = run_checkra1n("UDID123")
        assert result.success is False
        assert result.tool == "checkra1n"
        assert result.error == "process_error"
        assert "device not in DFU" in result.message

    @patch("app.services.bypass_tools.check_checkra1n_available", return_value=True)
    @patch("app.services.bypass_tools.subprocess.run")
    def test_progress_callback(self, mock_run, mock_avail):
        mock_run.return_value = MagicMock(returncode=0, stdout="Done", stderr="")
        cb = MagicMock()

        from app.services.bypass_tools import run_checkra1n

        result = run_checkra1n("UDID123", progress_cb=cb)
        assert result.success is True
        assert cb.call_count >= 2  # at least start + end messages


# ── TestBroqueAvailability ───────────────────────────────────


class TestBroqueAvailability:
    @patch("app.services.bypass_tools._BROQUE_DIR")
    def test_available(self, mock_dir):
        bypass_sh = MagicMock()
        bypass_sh.exists.return_value = True
        mock_dir.__truediv__ = MagicMock(return_value=bypass_sh)
        mock_dir.is_dir.return_value = True

        with patch.object(sys.modules["app.services.bypass_tools"], "sys") as mock_sys:
            mock_sys.platform = "linux"
            from app.services.bypass_tools import check_broque_available

            assert check_broque_available() is True

    @patch("app.services.bypass_tools._BROQUE_DIR")
    def test_not_available(self, mock_dir):
        mock_dir.is_dir.return_value = False

        from app.services.bypass_tools import check_broque_available

        assert check_broque_available() is False


# ── TestRunBroque ────────────────────────────────────────────


class TestRunBroque:
    @patch("app.services.bypass_tools.check_broque_available", return_value=False)
    def test_not_available_returns_failure(self, mock_avail):
        from app.services.bypass_tools import run_broque_bypass

        result = run_broque_bypass("UDID123")
        assert result.success is False
        assert result.tool == "broque"
        assert result.error == "not_available"

    @patch("app.services.bypass_tools.check_broque_available", return_value=True)
    @patch("app.services.bypass_tools.subprocess.run")
    def test_success(self, mock_run, mock_avail):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Bypass complete", stderr=""
        )

        from app.services.bypass_tools import run_broque_bypass

        result = run_broque_bypass("UDID123")
        assert result.success is True
        assert result.tool == "broque"
        assert result.error is None


# ── TestSSHRamdisk ───────────────────────────────────────────


class TestSSHRamdisk:
    @patch("app.services.bypass_tools.shutil.which", return_value=None)
    def test_not_available(self, mock_which):
        with patch.object(sys.modules["app.services.bypass_tools"], "sys") as mock_sys:
            mock_sys.platform = "linux"
            from app.services.bypass_tools import check_ssh_ramdisk_available

            assert check_ssh_ramdisk_available() is False

    @patch("app.services.bypass_tools.check_ssh_ramdisk_available", return_value=False)
    def test_boot_not_available(self, mock_avail):
        from app.services.bypass_tools import boot_ssh_ramdisk

        result = boot_ssh_ramdisk("UDID123")
        assert result.success is False
        assert result.tool == "ssh_ramdisk"
        assert result.error == "not_available"

    @patch("app.services.bypass_tools.check_ssh_ramdisk_available", return_value=True)
    @patch("app.services.bypass_tools.subprocess.run")
    def test_boot_success(self, mock_run, mock_avail):
        mock_run.return_value = MagicMock(returncode=0, stdout="Booted", stderr="")

        from app.services.bypass_tools import boot_ssh_ramdisk

        result = boot_ssh_ramdisk("UDID123")
        assert result.success is True
        assert result.tool == "ssh_ramdisk"


# ── TestExtractData ──────────────────────────────────────────


class TestExtractData:
    @patch("app.services.bypass_tools.check_ssh_ramdisk_available", return_value=True)
    @patch("app.services.bypass_tools.subprocess.run")
    def test_extract_photos(self, mock_run, mock_avail):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="3 files copied", stderr=""
        )

        from app.services.bypass_tools import extract_data

        result = extract_data("UDID123", "/tmp/extract", ["photos"])
        assert "photos" in result
        assert result["photos"]["success"] is True

    @patch("app.services.bypass_tools.check_ssh_ramdisk_available", return_value=False)
    def test_extract_tool_missing(self, mock_avail):
        from app.services.bypass_tools import extract_data

        result = extract_data("UDID123", "/tmp/extract", ["photos"])
        assert "photos" in result
        assert result["photos"]["success"] is False
