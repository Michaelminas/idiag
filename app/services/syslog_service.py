"""Syslog streaming service — parse, filter, and buffer device syslog lines."""

import collections
import logging
import re
from datetime import datetime
from typing import Generator, Optional

from app.models.tools import SyslogEntry, SyslogFilter

logger = logging.getLogger(__name__)

# Regex for standard syslog format: "Mon DD HH:MM:SS hostname process[pid]: message"
_SYSLOG_RE = re.compile(
    r"^(\w+\s+\d+\s+[\d:]+)\s+\S+\s+(\w[\w.-]*)(?:\[(\d+)\])?:\s*(.*)$"
)

# Keyword → level mapping (checked in order; first match wins)
_LEVEL_KEYWORDS: dict[str, list[str]] = {
    "Emergency": ["panic", "emergency"],
    "Alert": ["alert"],
    "Critical": ["critical", "fatal"],
    "Error": ["error", "fail", "exception"],
    "Warning": ["warn"],
    "Notice": ["notice"],
    "Debug": ["debug"],
}


def _infer_level(message: str) -> str:
    """Infer syslog severity level from message content keywords."""
    lower = message.lower()
    for level, keywords in _LEVEL_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return level
    return "Info"


def parse_syslog_line(line: str) -> Optional[SyslogEntry]:
    """Parse a raw syslog line into a SyslogEntry.

    Returns None for malformed or empty lines.
    """
    if not line or not line.strip():
        return None

    match = _SYSLOG_RE.match(line)
    if not match:
        return None

    time_str, process, pid_str, message = match.groups()

    try:
        timestamp = datetime.strptime(
            f"{datetime.now().year} {time_str}", "%Y %b %d %H:%M:%S"
        )
    except ValueError:
        return None

    pid = int(pid_str) if pid_str else 0
    level = _infer_level(message)

    return SyslogEntry(
        timestamp=timestamp,
        process=process,
        pid=pid,
        level=level,
        message=message,
    )


def filter_entry(entry: SyslogEntry, filt: SyslogFilter) -> bool:
    """Check whether a SyslogEntry passes all filter criteria (AND logic).

    An empty filter (all fields None) always returns True.
    """
    if filt.process is not None and entry.process != filt.process:
        return False
    if filt.level is not None and entry.level != filt.level:
        return False
    if filt.keyword is not None and filt.keyword.lower() not in entry.message.lower():
        return False
    return True


class SyslogBuffer:
    """Fixed-size ring buffer for SyslogEntry objects."""

    def __init__(self, max_size: int = 1000) -> None:
        self._buf: collections.deque[SyslogEntry] = collections.deque(maxlen=max_size)

    def add(self, entry: SyslogEntry) -> None:
        """Append an entry; oldest entries are dropped when full."""
        self._buf.append(entry)

    def get_all(self) -> list[SyslogEntry]:
        """Return a list copy of all buffered entries."""
        return list(self._buf)

    def clear(self) -> None:
        """Remove all entries from the buffer."""
        self._buf.clear()


def create_syslog_stream(udid: Optional[str] = None) -> Generator[str, None, None]:
    """Yield raw syslog lines from a connected iOS device via pymobiledevice3.

    Falls back gracefully if pymobiledevice3 is not installed.
    """
    try:
        from pymobiledevice3.lockdown import LockdownClient
        from pymobiledevice3.services.os_trace import OsTraceService
    except ImportError:
        logger.warning("pymobiledevice3 not available — cannot stream syslog")
        return

    try:
        lockdown = LockdownClient(udid=udid) if udid else LockdownClient()
        with OsTraceService(lockdown) as service:
            for entry in service.syslog():
                yield str(entry)
    except Exception:
        logger.exception("Syslog stream error")
