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
