"""Market pricing API routes."""

from fastapi import APIRouter

from app.services.pricing_service import lookup_price

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


@router.get("/lookup")
def price_lookup(model: str, storage_gb: int = 0, grade: str = "") -> dict:
    """Look up market pricing for a device model."""
    return lookup_price(model, storage_gb, grade)
