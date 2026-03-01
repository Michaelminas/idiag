"""Tests for app/models/tools.py — advanced tools Pydantic models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models.tools import (
    BypassResult,
    CableCheckResult,
    RestoreCompatibility,
    SyslogEntry,
    SyslogFilter,
)


# ── BypassResult ──────────────────────────────────────────────


class TestBypassResult:
    def test_defaults(self):
        r = BypassResult(success=True, tool="checkra1n")
        assert r.success is True
        assert r.tool == "checkra1n"
        assert r.error is None
        assert r.message is None
        assert r.timestamp is None

    def test_full(self):
        ts = datetime(2026, 3, 1, 12, 0, 0)
        r = BypassResult(
            success=False,
            tool="broque",
            error="device not in DFU",
            message="Please enter DFU mode first",
            timestamp=ts,
        )
        assert r.success is False
        assert r.tool == "broque"
        assert r.error == "device not in DFU"
        assert r.message == "Please enter DFU mode first"
        assert r.timestamp == ts

    def test_tool_literal(self):
        """Only checkra1n, broque, ssh_ramdisk are valid tools."""
        for valid in ("checkra1n", "broque", "ssh_ramdisk"):
            r = BypassResult(success=True, tool=valid)
            assert r.tool == valid

        with pytest.raises(ValidationError):
            BypassResult(success=True, tool="invalid_tool")


# ── RestoreCompatibility ─────────────────────────────────────


class TestRestoreCompatibility:
    def test_compatible(self):
        r = RestoreCompatibility(
            compatible=True,
            target_version="17.4",
            blob_valid=True,
            sep_compatible=True,
        )
        assert r.compatible is True
        assert r.target_version == "17.4"
        assert r.blob_valid is True
        assert r.sep_compatible is True
        assert r.reason is None

    def test_incompatible(self):
        r = RestoreCompatibility(
            compatible=False,
            target_version="16.0",
            blob_valid=True,
            sep_compatible=False,
            reason="SEP firmware is no longer signed",
        )
        assert r.compatible is False
        assert r.sep_compatible is False
        assert r.reason == "SEP firmware is no longer signed"


# ── SyslogEntry ──────────────────────────────────────────────


class TestSyslogEntry:
    def test_entry(self):
        ts = datetime(2026, 3, 1, 8, 30, 0)
        e = SyslogEntry(
            timestamp=ts,
            process="SpringBoard",
            pid=42,
            level="Error",
            message="Application crashed unexpectedly",
        )
        assert e.timestamp == ts
        assert e.process == "SpringBoard"
        assert e.pid == 42
        assert e.level == "Error"
        assert e.message == "Application crashed unexpectedly"

    def test_level_literal(self):
        """Only valid syslog levels are accepted."""
        valid_levels = [
            "Emergency", "Alert", "Critical", "Error",
            "Warning", "Notice", "Info", "Debug",
        ]
        for lvl in valid_levels:
            e = SyslogEntry(
                timestamp=datetime.now(),
                process="test",
                pid=1,
                level=lvl,
                message="msg",
            )
            assert e.level == lvl

        with pytest.raises(ValidationError):
            SyslogEntry(
                timestamp=datetime.now(),
                process="test",
                pid=1,
                level="Verbose",
                message="msg",
            )


# ── SyslogFilter ─────────────────────────────────────────────


class TestSyslogFilter:
    def test_defaults(self):
        f = SyslogFilter()
        assert f.process is None
        assert f.level is None
        assert f.keyword is None

    def test_with_values(self):
        f = SyslogFilter(process="SpringBoard", level="Error", keyword="crash")
        assert f.process == "SpringBoard"
        assert f.level == "Error"
        assert f.keyword == "crash"


# ── CableCheckResult ─────────────────────────────────────────


class TestCableCheckResult:
    def test_defaults(self):
        r = CableCheckResult(
            connection_type="USB-C",
            charge_capable=True,
            data_capable=True,
        )
        assert r.connection_type == "USB-C"
        assert r.charge_capable is True
        assert r.data_capable is True
        assert r.negotiated_speed is None
        assert r.warnings == []

    def test_with_warnings(self):
        r = CableCheckResult(
            connection_type="Lightning",
            charge_capable=True,
            data_capable=False,
            negotiated_speed="USB 2.0",
            warnings=["Data transfer not supported", "Cable may be charge-only"],
        )
        assert r.connection_type == "Lightning"
        assert r.data_capable is False
        assert r.negotiated_speed == "USB 2.0"
        assert len(r.warnings) == 2
        assert "Data transfer not supported" in r.warnings
