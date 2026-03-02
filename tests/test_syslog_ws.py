"""Tests for /ws/syslog/{udid} WebSocket endpoint."""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


class TestSyslogWebSocket:
    """Tests for the syslog WebSocket streaming endpoint."""

    def test_connect_and_receive_entry(self):
        """Client connects, sends filter, receives parsed syslog entry."""
        client = TestClient(app)
        mock_lines = [
            "Mar  2 10:30:45 iPhone kernel[0]: test message",
        ]
        with patch("app.api.websocket.create_syslog_stream") as mock_stream:
            mock_stream.return_value = iter(mock_lines)
            with client.websocket_connect("/ws/syslog/abc123") as ws:
                ws.send_json({"process": None, "level": None, "keyword": None})
                data = ws.receive_json()
                assert data["event"] == "syslog"
                assert data["data"]["process"] == "kernel"
                assert data["data"]["pid"] == 0
                assert "test message" in data["data"]["message"]

    def test_filter_by_process(self):
        """Only entries matching the process filter are sent."""
        client = TestClient(app)
        mock_lines = [
            "Mar  2 10:30:45 iPhone kernel[0]: kernel msg",
            "Mar  2 10:30:46 iPhone SpringBoard[100]: springboard msg",
            "Mar  2 10:30:47 iPhone kernel[0]: another kernel msg",
        ]
        with patch("app.api.websocket.create_syslog_stream") as mock_stream:
            mock_stream.return_value = iter(mock_lines)
            with client.websocket_connect("/ws/syslog/dev1") as ws:
                ws.send_json({"process": "kernel", "level": None, "keyword": None})
                d1 = ws.receive_json()
                assert d1["data"]["process"] == "kernel"
                d2 = ws.receive_json()
                assert d2["data"]["process"] == "kernel"
                assert "another kernel msg" in d2["data"]["message"]

    def test_filter_by_keyword(self):
        """Only entries matching the keyword filter are sent."""
        client = TestClient(app)
        mock_lines = [
            "Mar  2 10:30:45 iPhone kern[0]: error disk failure",
            "Mar  2 10:30:46 iPhone kern[0]: info all good",
            "Mar  2 10:30:47 iPhone kern[0]: error network timeout",
        ]
        with patch("app.api.websocket.create_syslog_stream") as mock_stream:
            mock_stream.return_value = iter(mock_lines)
            with client.websocket_connect("/ws/syslog/dev2") as ws:
                ws.send_json({"process": None, "level": None, "keyword": "error"})
                d1 = ws.receive_json()
                assert "error" in d1["data"]["message"].lower()
                d2 = ws.receive_json()
                assert "error" in d2["data"]["message"].lower()

    def test_malformed_lines_skipped(self):
        """Malformed syslog lines are silently skipped."""
        client = TestClient(app)
        mock_lines = [
            "this is garbage",
            "",
            "Mar  2 10:30:45 iPhone kernel[0]: valid line",
        ]
        with patch("app.api.websocket.create_syslog_stream") as mock_stream:
            mock_stream.return_value = iter(mock_lines)
            with client.websocket_connect("/ws/syslog/dev3") as ws:
                ws.send_json({"process": None, "level": None, "keyword": None})
                data = ws.receive_json()
                assert data["event"] == "syslog"
                assert data["data"]["process"] == "kernel"

    def test_no_filter_message_uses_defaults(self):
        """If client sends no filter within timeout, default (empty) filter is used."""
        client = TestClient(app)
        mock_lines = [
            "Mar  2 10:30:45 iPhone kernel[0]: test default",
        ]
        with patch("app.api.websocket.create_syslog_stream") as mock_stream:
            mock_stream.return_value = iter(mock_lines)
            # Patch the timeout so we don't wait 5s in tests
            with patch("app.api.websocket.SYSLOG_FILTER_TIMEOUT", 0.1):
                with client.websocket_connect("/ws/syslog/dev4") as ws:
                    # Don't send any filter — should still get entries
                    data = ws.receive_json()
                    assert data["event"] == "syslog"
                    assert data["data"]["process"] == "kernel"

    def test_empty_stream(self):
        """If the syslog stream yields no lines, connection closes cleanly."""
        client = TestClient(app)
        with patch("app.api.websocket.create_syslog_stream") as mock_stream:
            mock_stream.return_value = iter([])
            with client.websocket_connect("/ws/syslog/dev5") as ws:
                ws.send_json({"process": None, "level": None, "keyword": None})
                # Stream is exhausted; the endpoint should close the connection.
                # Trying to receive should raise or return close.

    def test_stream_called_with_udid(self):
        """create_syslog_stream is called with the correct udid from the URL."""
        client = TestClient(app)
        with patch("app.api.websocket.create_syslog_stream") as mock_stream:
            mock_stream.return_value = iter([])
            with client.websocket_connect("/ws/syslog/MYUDID999") as ws:
                ws.send_json({"process": None, "level": None, "keyword": None})
            mock_stream.assert_called_once_with("MYUDID999")

    def test_filter_by_level(self):
        """Only entries matching the level filter are sent."""
        client = TestClient(app)
        mock_lines = [
            "Mar  2 10:30:45 iPhone kern[0]: error happened here",
            "Mar  2 10:30:46 iPhone kern[0]: just a debug trace",
            "Mar  2 10:30:47 iPhone kern[0]: another error found",
        ]
        with patch("app.api.websocket.create_syslog_stream") as mock_stream:
            mock_stream.return_value = iter(mock_lines)
            with client.websocket_connect("/ws/syslog/dev6") as ws:
                ws.send_json({"process": None, "level": "Error", "keyword": None})
                d1 = ws.receive_json()
                assert d1["data"]["level"] == "Error"
                d2 = ws.receive_json()
                assert d2["data"]["level"] == "Error"
