"""Tests for the unified snapshot API endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestSnapshotEndpoint:
    @patch("app.api.diagnostics.device_service.get_device_info")
    @patch("app.api.diagnostics.diagnostic_engine.run_diagnostics")
    @patch("app.api.diagnostics.log_analyzer.analyze_device")
    @patch("app.api.diagnostics.verification_service.run_verification", new_callable=AsyncMock)
    @patch("app.api.diagnostics.calculate_grade")
    def test_snapshot_returns_all_fields(
        self, mock_grade, mock_verif, mock_crashes, mock_diag, mock_info
    ):
        from app.models.device import DeviceInfo
        from app.models.diagnostic import DiagnosticResult, BatteryInfo
        from app.models.crash import CrashAnalysis
        from app.models.verification import VerificationResult
        from app.models.grading import DeviceGrade

        mock_info.return_value = DeviceInfo(
            udid="test-udid", serial="DNPXXXXXXXX", imei="353462111234567",
            product_type="iPhone14,2",
        )
        mock_diag.return_value = DiagnosticResult(battery=BatteryInfo(health_percent=95.0))
        mock_crashes.return_value = CrashAnalysis(total_reports=5)
        mock_verif.return_value = VerificationResult(blacklist_status="clean")
        mock_grade.return_value = DeviceGrade(overall_grade="A", overall_score=3.8)

        resp = client.get("/api/diagnostics/snapshot/test-udid")
        assert resp.status_code == 200
        data = resp.json()
        assert data["info"]["udid"] == "test-udid"
        assert data["diagnostics"]["battery"]["health_percent"] == 95.0
        assert data["crash_analysis"]["total_reports"] == 5
        assert data["verification"]["blacklist_status"] == "clean"
        assert data["grade"]["overall_grade"] == "A"

    @patch("app.api.diagnostics.device_service.get_device_info")
    def test_snapshot_404_when_no_device(self, mock_info):
        mock_info.return_value = None
        resp = client.get("/api/diagnostics/snapshot/nonexistent")
        assert resp.status_code == 404
