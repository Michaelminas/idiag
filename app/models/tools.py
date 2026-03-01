"""Advanced tools models — bypass, restore compatibility, syslog, cable check."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class BypassResult(BaseModel):
    """Result of an activation-lock or passcode bypass attempt."""

    success: bool
    tool: Literal["checkra1n", "broque", "ssh_ramdisk"]
    error: Optional[str] = None
    message: Optional[str] = None
    timestamp: Optional[datetime] = None


class RestoreCompatibility(BaseModel):
    """Pre-flight check for SHSH blob restore viability."""

    compatible: bool
    target_version: str
    blob_valid: bool
    sep_compatible: bool
    reason: Optional[str] = None


SyslogLevel = Literal[
    "Emergency", "Alert", "Critical", "Error",
    "Warning", "Notice", "Info", "Debug",
]


class SyslogEntry(BaseModel):
    """A single parsed syslog line from a device."""

    timestamp: datetime
    process: str
    pid: int
    level: SyslogLevel
    message: str


class SyslogFilter(BaseModel):
    """Filter criteria for syslog streaming."""

    process: Optional[str] = None
    level: Optional[str] = None
    keyword: Optional[str] = None


class CableCheckResult(BaseModel):
    """USB/Lightning cable diagnostic result."""

    connection_type: str
    charge_capable: bool
    data_capable: bool
    negotiated_speed: Optional[str] = None
    warnings: list[str] = []
