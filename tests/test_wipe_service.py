"""Tests for wipe service — device erasure and certificate generation."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.firmware import WipeRecord


class TestEraseDevice:
    """Test device factory reset (mocked pymobiledevice3)."""

    @patch("app.services.wipe_service._perform_erase")
    def test_erase_success(self, mock_erase):
        from app.services.wipe_service import erase_device

        mock_erase.return_value = True
        result = erase_device("test-udid")
        assert result is True

    @patch("app.services.wipe_service._perform_erase")
    def test_erase_failure(self, mock_erase):
        from app.services.wipe_service import erase_device

        mock_erase.side_effect = Exception("Device locked")
        result = erase_device("test-udid")
        assert result is False


class TestCertificateGeneration:
    """Test erasure certificate PDF generation."""

    def test_render_certificate_html(self):
        from app.services.wipe_service import render_certificate_html

        record = WipeRecord(
            device_id=1, udid="ABCD1234", serial="C39TEST123",
            imei="353456789012345", model="iPhone 13 Pro",
            ios_version="17.4", method="factory_reset",
            timestamp=datetime(2026, 3, 1, 12, 0, 0),
            operator="TestUser", success=True,
        )
        html = render_certificate_html(record)
        assert "C39TEST123" in html
        assert "353456789012345" in html
        assert "iPhone 13 Pro" in html
        assert "factory_reset" in html

    @patch("app.services.wipe_service._html_to_pdf")
    def test_generate_certificate_pdf(self, mock_pdf, tmp_path):
        from app.services.wipe_service import generate_certificate

        mock_pdf.return_value = True

        record = WipeRecord(
            device_id=1, udid="ABCD1234", serial="C39TEST123",
            imei="353456789012345", model="iPhone 13 Pro",
            ios_version="17.4", method="factory_reset",
            timestamp=datetime(2026, 3, 1, 12, 0, 0),
            operator="TestUser", success=True,
        )

        cert_path = generate_certificate(record, output_dir=tmp_path)
        assert cert_path is not None
        assert "C39TEST123" in cert_path.name
        mock_pdf.assert_called_once()
