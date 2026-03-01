"""Tests for app/services/syslog_service.py — syslog parsing, filtering, buffering."""

from datetime import datetime

import pytest

from app.models.tools import SyslogEntry, SyslogFilter


# ── TestParseSyslogLine ─────────────────────────────────────


class TestParseSyslogLine:
    def test_standard_line(self):
        from app.services.syslog_service import parse_syslog_line

        line = "Jan  5 12:34:56 iPhone SpringBoard[100]: Launched app com.example"
        entry = parse_syslog_line(line)
        assert entry is not None
        assert entry.process == "SpringBoard"
        assert entry.pid == 100
        assert entry.message == "Launched app com.example"
        assert entry.level == "Info"
        assert entry.timestamp.month == 1
        assert entry.timestamp.day == 5
        assert entry.timestamp.hour == 12

    def test_process_with_pid(self):
        from app.services.syslog_service import parse_syslog_line

        line = "Mar  2 08:00:01 myhost kernel[0]: error: disk I/O failure"
        entry = parse_syslog_line(line)
        assert entry is not None
        assert entry.process == "kernel"
        assert entry.pid == 0
        assert entry.level == "Error"
        assert "disk I/O failure" in entry.message

    def test_malformed_line(self):
        from app.services.syslog_service import parse_syslog_line

        result = parse_syslog_line("this is not a syslog line at all")
        assert result is None

    def test_empty_line(self):
        from app.services.syslog_service import parse_syslog_line

        assert parse_syslog_line("") is None
        assert parse_syslog_line("   ") is None

    def test_process_without_pid(self):
        from app.services.syslog_service import parse_syslog_line

        line = "Feb 10 09:15:30 device syslog: system warning detected"
        entry = parse_syslog_line(line)
        assert entry is not None
        assert entry.process == "syslog"
        assert entry.pid == 0
        assert entry.level == "Warning"

    def test_level_panic(self):
        from app.services.syslog_service import parse_syslog_line

        line = "Jan  1 00:00:00 host kern[1]: kernel panic - not syncing"
        entry = parse_syslog_line(line)
        assert entry is not None
        assert entry.level == "Emergency"

    def test_level_critical(self):
        from app.services.syslog_service import parse_syslog_line

        line = "Jan  1 00:00:00 host proc[1]: fatal error encountered"
        entry = parse_syslog_line(line)
        assert entry is not None
        assert entry.level == "Critical"

    def test_level_debug(self):
        from app.services.syslog_service import parse_syslog_line

        line = "Jan  1 00:00:00 host proc[1]: debug trace output"
        entry = parse_syslog_line(line)
        assert entry is not None
        assert entry.level == "Debug"


# ── TestFilterEntry ─────────────────────────────────────────


class TestFilterEntry:
    @pytest.fixture
    def sample_entry(self):
        return SyslogEntry(
            timestamp=datetime(2026, 1, 5, 12, 34, 56),
            process="SpringBoard",
            pid=100,
            level="Error",
            message="Failed to launch application",
        )

    def test_no_filter(self, sample_entry):
        from app.services.syslog_service import filter_entry

        filt = SyslogFilter()
        assert filter_entry(sample_entry, filt) is True

    def test_process_filter_match(self, sample_entry):
        from app.services.syslog_service import filter_entry

        filt = SyslogFilter(process="SpringBoard")
        assert filter_entry(sample_entry, filt) is True

    def test_process_filter_no_match(self, sample_entry):
        from app.services.syslog_service import filter_entry

        filt = SyslogFilter(process="kernel")
        assert filter_entry(sample_entry, filt) is False

    def test_level_filter(self, sample_entry):
        from app.services.syslog_service import filter_entry

        filt = SyslogFilter(level="Error")
        assert filter_entry(sample_entry, filt) is True

        filt2 = SyslogFilter(level="Warning")
        assert filter_entry(sample_entry, filt2) is False

    def test_keyword_filter(self, sample_entry):
        from app.services.syslog_service import filter_entry

        filt = SyslogFilter(keyword="launch")
        assert filter_entry(sample_entry, filt) is True

        filt2 = SyslogFilter(keyword="crash")
        assert filter_entry(sample_entry, filt2) is False

    def test_keyword_case_insensitive(self, sample_entry):
        from app.services.syslog_service import filter_entry

        filt = SyslogFilter(keyword="FAILED")
        assert filter_entry(sample_entry, filt) is True

    def test_combined_filters(self, sample_entry):
        from app.services.syslog_service import filter_entry

        filt = SyslogFilter(process="SpringBoard", level="Error", keyword="launch")
        assert filter_entry(sample_entry, filt) is True

    def test_combined_partial_mismatch(self, sample_entry):
        from app.services.syslog_service import filter_entry

        # Process matches but level doesn't
        filt = SyslogFilter(process="SpringBoard", level="Warning")
        assert filter_entry(sample_entry, filt) is False


# ── TestSyslogBuffer ────────────────────────────────────────


class TestSyslogBuffer:
    def _make_entry(self, msg: str) -> SyslogEntry:
        return SyslogEntry(
            timestamp=datetime(2026, 1, 1, 0, 0, 0),
            process="test",
            pid=1,
            level="Info",
            message=msg,
        )

    def test_add_and_get(self):
        from app.services.syslog_service import SyslogBuffer

        buf = SyslogBuffer(max_size=10)
        e1 = self._make_entry("one")
        e2 = self._make_entry("two")
        buf.add(e1)
        buf.add(e2)
        result = buf.get_all()
        assert len(result) == 2
        assert result[0].message == "one"
        assert result[1].message == "two"
        # get_all returns a copy, not the internal deque
        assert isinstance(result, list)

    def test_overflow(self):
        from app.services.syslog_service import SyslogBuffer

        buf = SyslogBuffer(max_size=3)
        for i in range(5):
            buf.add(self._make_entry(f"msg-{i}"))
        result = buf.get_all()
        assert len(result) == 3
        # oldest entries should be dropped
        assert result[0].message == "msg-2"
        assert result[1].message == "msg-3"
        assert result[2].message == "msg-4"

    def test_clear(self):
        from app.services.syslog_service import SyslogBuffer

        buf = SyslogBuffer(max_size=10)
        buf.add(self._make_entry("x"))
        buf.clear()
        assert len(buf.get_all()) == 0
