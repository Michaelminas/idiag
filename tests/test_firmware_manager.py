"""Tests for firmware manager service."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.firmware import FirmwareVersion


# -- Fixture: mock ipsw.me API response --

IPSW_API_RESPONSE = {
    "name": "iPhone 13 Pro",
    "identifier": "iPhone14,2",
    "firmwares": [
        {
            "identifier": "iPhone14,2",
            "version": "17.4",
            "buildid": "21E219",
            "sha1sum": "abc123def456",
            "url": "https://updates.cdn-apple.com/fake/iPhone14,2_17.4_21E219.ipsw",
            "filesize": 6_500_000_000,
            "signed": True,
        },
        {
            "identifier": "iPhone14,2",
            "version": "17.3.1",
            "buildid": "21D61",
            "sha1sum": "789ghi012jkl",
            "url": "https://updates.cdn-apple.com/fake/iPhone14,2_17.3.1_21D61.ipsw",
            "filesize": 6_400_000_000,
            "signed": False,
        },
    ],
}


class TestGetSignedVersions:
    """Test TSS signing status lookup via ipsw.me API."""

    @patch("app.services.firmware_manager.httpx")
    def test_returns_signed_versions(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = IPSW_API_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        from app.services.firmware_manager import get_signed_versions

        versions = get_signed_versions("iPhone14,2")

        assert len(versions) == 1
        assert versions[0].version == "17.4"
        assert versions[0].signed is True
        assert versions[0].sha1 == "abc123def456"

    @patch("app.services.firmware_manager.httpx")
    def test_returns_all_versions_when_signed_only_false(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = IPSW_API_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        from app.services.firmware_manager import get_signed_versions

        versions = get_signed_versions("iPhone14,2", signed_only=False)
        assert len(versions) == 2

    @patch("app.services.firmware_manager.httpx")
    def test_returns_empty_on_api_error(self, mock_httpx):
        mock_httpx.get.side_effect = Exception("Network error")

        from app.services.firmware_manager import get_signed_versions

        versions = get_signed_versions("iPhone14,2")
        assert versions == []


class TestIPSWCache:
    """Test IPSW download and LRU cache logic."""

    def test_list_cached_empty(self, tmp_path):
        from app.services.firmware_manager import list_cached_ipsw
        entries = list_cached_ipsw(cache_dir=tmp_path)
        assert entries == []

    def test_cache_entry_creation_and_listing(self, tmp_path):
        """Simulate a cached IPSW and verify listing."""
        from app.services.firmware_manager import list_cached_ipsw, _ipsw_filename

        fname = _ipsw_filename("iPhone14,2", "17.4", "21E219")
        fpath = tmp_path / fname
        fpath.write_bytes(b"fake ipsw content")

        entries = list_cached_ipsw(cache_dir=tmp_path)
        assert len(entries) == 1
        assert entries[0].model == "iPhone14,2"
        assert entries[0].version == "17.4"

    def test_evict_cache_oldest_first(self, tmp_path):
        """LRU eviction should remove oldest files first."""
        import time
        from app.services.firmware_manager import evict_cache, _ipsw_filename

        # Create 3 "IPSW" files with different timestamps
        for i, (model, ver) in enumerate([
            ("iPhone14,2", "17.3"), ("iPhone14,2", "17.4"), ("iPhone15,2", "17.4")
        ]):
            fpath = tmp_path / _ipsw_filename(model, ver, f"BUILD{i}")
            fpath.write_bytes(b"x" * 1000)
            time.sleep(0.05)  # ensure different mtime

        # Evict with max_bytes = 2500 (keeps 2 of 3)
        evict_cache(cache_dir=tmp_path, max_bytes=2500)
        remaining = list(tmp_path.glob("*.ipsw"))
        assert len(remaining) == 2

    def test_verify_sha1(self, tmp_path):
        """SHA1 verification of a downloaded file."""
        from app.services.firmware_manager import verify_sha1

        fpath = tmp_path / "test.ipsw"
        content = b"test firmware content"
        fpath.write_bytes(content)

        import hashlib
        expected = hashlib.sha1(content).hexdigest()
        assert verify_sha1(fpath, expected) is True
        assert verify_sha1(fpath, "wrong_hash") is False

    def test_get_cached_ipsw_found(self, tmp_path):
        from app.services.firmware_manager import get_cached_ipsw, _ipsw_filename
        fname = _ipsw_filename("iPhone14,2", "17.4", "21E219")
        (tmp_path / fname).write_bytes(b"data")
        result = get_cached_ipsw("iPhone14,2", "17.4", cache_dir=tmp_path)
        assert result is not None

    def test_get_cached_ipsw_not_found(self, tmp_path):
        from app.services.firmware_manager import get_cached_ipsw
        result = get_cached_ipsw("iPhone14,2", "17.4", cache_dir=tmp_path)
        assert result is None


class TestSHSHBlobs:
    """Test SHSH blob save with tsschecker + pymobiledevice3 fallback."""

    @patch("app.services.firmware_manager._save_via_tsschecker")
    def test_save_shsh_via_tsschecker(self, mock_tsschecker, tmp_path):
        from app.services.firmware_manager import save_shsh_blobs

        blob_file = tmp_path / "blob.shsh2"
        blob_file.write_bytes(b"fake-shsh-blob-data")
        mock_tsschecker.return_value = blob_file

        result = save_shsh_blobs(
            ecid="0x1234ABCD",
            device_model="iPhone14,2",
            ios_version="17.4",
            blob_dir=tmp_path,
        )

        assert result is not None
        assert result.exists()
        mock_tsschecker.assert_called_once()

    @patch("app.services.firmware_manager._save_via_pymobiledevice3")
    @patch("app.services.firmware_manager._save_via_tsschecker", return_value=None)
    def test_falls_back_to_pymobiledevice3(self, _mock_tss, mock_pmd3, tmp_path):
        from app.services.firmware_manager import save_shsh_blobs

        blob_file = tmp_path / "fallback.shsh2"
        blob_file.write_bytes(b"pmd3-blob-data")
        mock_pmd3.return_value = blob_file

        result = save_shsh_blobs(
            ecid="0x1234ABCD",
            device_model="iPhone14,2",
            ios_version="17.4",
            blob_dir=tmp_path,
        )

        assert result is not None
        assert result.exists()
        mock_pmd3.assert_called_once()

    @patch("app.services.firmware_manager._save_via_pymobiledevice3", return_value=None)
    @patch("app.services.firmware_manager._save_via_tsschecker", return_value=None)
    def test_both_methods_fail(self, _mock_tss, _mock_pmd3, tmp_path):
        from app.services.firmware_manager import save_shsh_blobs

        result = save_shsh_blobs(
            ecid="0x1234ABCD",
            device_model="iPhone14,2",
            ios_version="17.4",
            blob_dir=tmp_path,
        )
        assert result is None


class TestDeviceModeHelpers:
    """Test DFU/Recovery mode entry/exit (mocked pymobiledevice3)."""

    @patch("app.services.firmware_manager._create_lockdown")
    def test_enter_recovery_mode(self, mock_lockdown_factory):
        from app.services.firmware_manager import enter_recovery_mode

        mock_lockdown = MagicMock()
        mock_lockdown_factory.return_value.__enter__ = MagicMock(return_value=mock_lockdown)
        mock_lockdown_factory.return_value.__exit__ = MagicMock(return_value=False)

        result = enter_recovery_mode("test-udid")
        assert result is True

    @patch("app.services.firmware_manager._create_lockdown")
    def test_enter_recovery_mode_failure(self, mock_lockdown_factory):
        from app.services.firmware_manager import enter_recovery_mode

        mock_lockdown_factory.side_effect = Exception("No device")
        result = enter_recovery_mode("test-udid")
        assert result is False

    @patch("app.services.firmware_manager._exit_recovery")
    def test_exit_recovery_mode(self, mock_exit):
        from app.services.firmware_manager import exit_recovery_mode

        mock_exit.return_value = True
        result = exit_recovery_mode("test-udid")
        assert result is True

    def test_get_device_mode_normal(self):
        from app.services.firmware_manager import get_device_mode

        with patch("app.services.firmware_manager._create_lockdown") as mock_ld:
            mock_lockdown = MagicMock()
            mock_ld.return_value.__enter__ = MagicMock(return_value=mock_lockdown)
            mock_ld.return_value.__exit__ = MagicMock(return_value=False)
            mode = get_device_mode("test-udid")
            assert mode == "normal"

    def test_get_device_mode_no_device(self):
        from app.services.firmware_manager import get_device_mode

        with patch("app.services.firmware_manager._create_lockdown") as mock_ld:
            mock_ld.side_effect = Exception("Not found")
            with patch("app.services.firmware_manager._check_recovery_mode") as mock_rec:
                mock_rec.return_value = False
                with patch("app.services.firmware_manager._check_dfu_mode") as mock_dfu:
                    mock_dfu.return_value = False
                    mode = get_device_mode("test-udid")
                    assert mode == "unknown"


class TestRestore:
    """Test firmware restore orchestration (mocked)."""

    @patch("app.services.firmware_manager._perform_restore")
    @patch("app.services.firmware_manager.download_ipsw")
    @patch("app.services.firmware_manager.get_signed_versions")
    def test_restore_device_success(self, mock_signed, mock_download, mock_restore, tmp_path):
        from app.services.firmware_manager import restore_device
        from app.models.firmware import FirmwareVersion

        mock_signed.return_value = [FirmwareVersion(
            version="17.4", build_id="21E219", model="iPhone14,2",
            url="https://example.com/fw.ipsw", sha1="abc123", size_bytes=1000, signed=True,
        )]
        fake_ipsw = tmp_path / "fw.ipsw"
        fake_ipsw.write_bytes(b"firmware")
        mock_download.return_value = fake_ipsw
        mock_restore.return_value = True

        progress_log = []
        result = restore_device(
            udid="test-udid",
            model="iPhone14,2",
            progress_callback=lambda p: progress_log.append(p),
        )
        assert result is True
        assert any(p.stage == "restoring" for p in progress_log)

    @patch("app.services.firmware_manager.get_signed_versions")
    def test_restore_no_signed_version(self, mock_signed):
        from app.services.firmware_manager import restore_device

        mock_signed.return_value = []

        progress_log = []
        result = restore_device(
            udid="test-udid",
            model="iPhone14,2",
            progress_callback=lambda p: progress_log.append(p),
        )
        assert result is False
        assert any(p.stage == "error" for p in progress_log)
