"""Verification check result models."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class VerificationResult(BaseModel):
    """Results from SICKW API + local activation check."""

    id: Optional[int] = None
    device_id: Optional[int] = None
    timestamp: Optional[datetime] = None
    blacklist_status: str = "unknown"  # clean / blacklisted / unknown
    fmi_status: str = "unknown"  # off / on / unknown
    carrier: str = ""
    carrier_locked: bool = False
    sim_lock_status: str = ""
    activation_state: str = ""  # Activated / Unactivated
    mdm_enrolled: bool = False
    mdm_organization: str = ""
    raw: dict[str, Any] = {}
