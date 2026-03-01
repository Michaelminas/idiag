"""Tests for PDF report generator."""

from app.models.device import DeviceRecord
from app.models.diagnostic import BatteryInfo, DiagnosticResult, PartsOriginality, StorageInfo
from app.models.verification import VerificationResult
from app.services.report_generator import generate_report_html


class TestReportGenerator:
    def test_html_renders_device_info(self):
        device = DeviceRecord(udid="test-001", serial="C8QH6T96DPNG",
                              model="iPhone 13 Pro", ios_version="17.4")
        html = generate_report_html(device)
        assert "iPhone 13 Pro" in html
        assert "C8QH6T96DPNG" in html
        assert "17.4" in html

    def test_html_renders_diagnostics(self):
        device = DeviceRecord(udid="test-001", model="iPhone 12")
        diag = DiagnosticResult(
            battery=BatteryInfo(health_percent=87.5, cycle_count=423),
            parts=PartsOriginality(all_original=True),
            storage=StorageInfo(total_gb=256.0, used_gb=128.0, available_gb=128.0),
        )
        html = generate_report_html(device, diagnostics=diag)
        assert "87.5%" in html
        assert "423" in html
        assert "256.0 GB" in html

    def test_html_renders_verification(self):
        device = DeviceRecord(udid="test-001")
        verif = VerificationResult(blacklist_status="clean", fmi_status="off",
                                   carrier="T-Mobile", carrier_locked=False)
        html = generate_report_html(device, verification=verif)
        assert "clean" in html
        assert "T-Mobile" in html
        assert "Unlocked" in html

    def test_html_renders_grade(self):
        device = DeviceRecord(udid="test-001")
        html = generate_report_html(device, grade="B+")
        assert "B+" in html
        assert "grade-b" in html

    def test_html_handles_no_data(self):
        device = DeviceRecord(udid="test-001")
        html = generate_report_html(device)
        assert "iDiag Health Report" in html
        assert "N/A" in html
