"""Tests for app/services/futurerestore.py — FutureRestore downgrade/upgrade service."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.tools import BypassResult, RestoreCompatibility


# -- TestFutureRestoreAvailability -------------------------------------------


class TestFutureRestoreAvailability:
    @patch("app.services.futurerestore.shutil.which", return_value="/usr/local/bin/futurerestore")
    def test_available(self, mock_which):
        from app.services.futurerestore import check_futurerestore_available

        assert check_futurerestore_available() is True
        mock_which.assert_called_once_with("futurerestore")

    @patch("app.services.futurerestore.shutil.which", return_value=None)
    def test_not_available(self, mock_which):
        from app.services.futurerestore import check_futurerestore_available

        assert check_futurerestore_available() is False


# -- TestCheckCompatibility --------------------------------------------------


class TestCheckCompatibility:
    def test_blob_not_found(self, tmp_path):
        from app.services.futurerestore import check_compatibility

        blob_path = tmp_path / "nonexistent.shsh2"
        result = check_compatibility("iPhone14,2", "16.0", blob_path)
        assert isinstance(result, RestoreCompatibility)
        assert result.compatible is False
        assert result.blob_valid is False
        assert "not found" in result.reason.lower()

    def test_valid_blob(self, tmp_path):
        from app.services.futurerestore import check_compatibility

        blob_path = tmp_path / "valid.shsh2"
        blob_path.write_text("<?xml ...><dict><key>ApImg4Ticket</key>...</dict>")
        result = check_compatibility("iPhone14,2", "16.0", blob_path)
        assert isinstance(result, RestoreCompatibility)
        assert result.compatible is True
        assert result.blob_valid is True
        assert result.sep_compatible is True
        assert result.target_version == "16.0"

    def test_empty_blob(self, tmp_path):
        from app.services.futurerestore import check_compatibility

        blob_path = tmp_path / "empty.shsh2"
        blob_path.write_text("")
        result = check_compatibility("iPhone14,2", "16.0", blob_path)
        assert isinstance(result, RestoreCompatibility)
        assert result.compatible is False
        assert result.blob_valid is False
        assert "empty" in result.reason.lower()


# -- TestRunFutureRestore ----------------------------------------------------


class TestRunFutureRestore:
    @patch("app.services.futurerestore.check_futurerestore_available", return_value=False)
    def test_not_available(self, mock_avail):
        from app.services.futurerestore import run_futurerestore

        result = run_futurerestore("UDID123", Path("/tmp/fw.ipsw"), Path("/tmp/blob.shsh2"))
        assert isinstance(result, BypassResult)
        assert result.success is False
        assert result.tool == "futurerestore"
        assert result.error == "not_available"

    @patch("app.services.futurerestore.check_futurerestore_available", return_value=True)
    @patch("app.services.futurerestore.subprocess.run")
    def test_success(self, mock_run, mock_avail):
        mock_run.return_value = MagicMock(returncode=0, stdout="Restore finished", stderr="")

        from app.services.futurerestore import run_futurerestore

        result = run_futurerestore("UDID123", Path("/tmp/fw.ipsw"), Path("/tmp/blob.shsh2"))
        assert result.success is True
        assert result.tool == "futurerestore"
        assert result.error is None

        # Verify the command was built correctly
        cmd = mock_run.call_args[0][0]
        assert "futurerestore" in cmd
        assert "-t" in cmd
        assert "--latest-sep" in cmd
        assert "--latest-baseband" in cmd
        assert "--set-nonce" in cmd

    @patch("app.services.futurerestore.check_futurerestore_available", return_value=True)
    @patch("app.services.futurerestore.subprocess.run")
    def test_failure(self, mock_run, mock_avail):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Error: SEP not compatible"
        )

        from app.services.futurerestore import run_futurerestore

        result = run_futurerestore("UDID123", Path("/tmp/fw.ipsw"), Path("/tmp/blob.shsh2"))
        assert result.success is False
        assert result.tool == "futurerestore"
        assert result.error == "process_error"
        assert "SEP not compatible" in result.message

    @patch("app.services.futurerestore.check_futurerestore_available", return_value=True)
    @patch(
        "app.services.futurerestore.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="futurerestore", timeout=1800),
    )
    def test_timeout(self, mock_run, mock_avail):
        from app.services.futurerestore import run_futurerestore

        result = run_futurerestore("UDID123", Path("/tmp/fw.ipsw"), Path("/tmp/blob.shsh2"))
        assert result.success is False
        assert result.tool == "futurerestore"
        assert result.error == "timeout"

    @patch("app.services.futurerestore.check_futurerestore_available", return_value=True)
    @patch("app.services.futurerestore.subprocess.run")
    def test_progress_callback(self, mock_run, mock_avail):
        mock_run.return_value = MagicMock(returncode=0, stdout="Done", stderr="")
        cb = MagicMock()

        from app.services.futurerestore import run_futurerestore

        result = run_futurerestore(
            "UDID123", Path("/tmp/fw.ipsw"), Path("/tmp/blob.shsh2"), progress_cb=cb
        )
        assert result.success is True
        assert cb.call_count >= 2  # at least start + end messages
