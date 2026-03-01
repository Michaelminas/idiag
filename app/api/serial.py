"""Serial decode & fraud detection API routes."""

from fastapi import APIRouter

from app.models.inventory import FraudCheck, IMEIValidation, SerialDecoded
from app.services.serial_decoder import cross_reference_check, decode_serial, validate_imei

router = APIRouter(prefix="/api/serial", tags=["serial"])


@router.get("/decode/{serial}")
def decode_serial_endpoint(serial: str) -> SerialDecoded:
    """Decode an Apple serial number (factory, date, model code)."""
    return decode_serial(serial)


@router.get("/validate-imei/{imei}")
def validate_imei_endpoint(imei: str) -> IMEIValidation:
    """Validate an IMEI using the Luhn algorithm."""
    return validate_imei(imei)


@router.get("/fraud-check")
def fraud_check_endpoint(
    serial: str, model_number: str, product_type: str, imei: str = ""
) -> FraudCheck:
    """Cross-reference device identifiers for fraud detection."""
    return cross_reference_check(serial, model_number, product_type, imei)
