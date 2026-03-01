"""Sales, photo, and listing models."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

Platform = Literal["ebay", "marketplace", "local", "other"]
PhotoLabel = Literal["front", "back", "screen", "side", "other"]


class PhotoRecord(BaseModel):
    id: Optional[int] = None
    device_id: int
    filename: str = ""
    filepath: str = ""
    label: PhotoLabel = "other"
    created_at: Optional[datetime] = None


class SalesRecord(BaseModel):
    id: Optional[int] = None
    device_id: int
    sell_price: Optional[float] = None
    platform: Platform = "local"
    fees: float = 0.0
    sold_at: Optional[datetime] = None
    days_in_inventory: Optional[int] = None
    profit: Optional[float] = None
    notes: str = ""
    created_at: Optional[datetime] = None


class ListingTemplate(BaseModel):
    platform: Platform
    title: str = ""
    description: str = ""
    price: Optional[float] = None
    condition: str = ""
