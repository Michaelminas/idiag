"""Tests for serial_decoder — pure logic, no device needed."""

from app.services.serial_decoder import (
    cross_reference_check,
    decode_serial,
    validate_imei,
)


class TestDecodeSerial:
    def test_old_format_decodes(self):
        result = decode_serial("C8QH6T96DPNG")
        assert not result.is_randomized
        assert "Zhengzhou" in result.factory
        assert result.half == "first"
        assert 2012 in result.year_candidates or 2022 in result.year_candidates
        assert result.week_in_half == 6
        assert result.model_code == "DPNG"

    def test_randomized_format(self):
        # 'A' at position 3 is NOT a valid year code -> randomized
        result = decode_serial("XXXA12345678")
        assert result.is_randomized

    def test_short_serial_is_randomized(self):
        result = decode_serial("SHORT")
        assert result.is_randomized

    def test_second_half_week_offset(self):
        # Factory "C8Q" (3 chars), then 'D' at position 3 = year 0, second half
        result = decode_serial("C8QD3T96DPNG")
        assert result.half == "second"
        # '3' at position 4 -> week 3 in half -> week 30 of year
        assert result.week_in_half == 3
        assert result.week_of_year == 30

    def test_factory_3char(self):
        result = decode_serial("C8QH6T96DPNG")
        assert result.factory == "Foxconn, Zhengzhou, China"

    def test_factory_2char(self):
        # "FK" + valid year char 'H' at position 3 -> factory resolves to 2-char "FK"
        result = decode_serial("FKHC12345678"[:12])
        assert "Zhengzhou" in result.factory

    def test_unknown_factory(self):
        result = decode_serial("ZZZH6T96DPNG")
        assert "Unknown" in result.factory


class TestValidateIMEI:
    def test_valid_imei(self):
        # Standard test IMEI with correct Luhn
        result = validate_imei("490154203237518")
        assert result.is_valid
        assert result.luhn_valid
        assert result.tac == "49015420"

    def test_invalid_luhn(self):
        result = validate_imei("490154203237519")  # wrong check digit
        assert not result.is_valid
        assert not result.luhn_valid
        assert len(result.notes) > 0

    def test_wrong_length(self):
        result = validate_imei("12345")
        assert not result.is_valid
        assert "15 digits" in result.notes[0]

    def test_non_digit(self):
        result = validate_imei("49015420323ABCD")
        assert not result.is_valid

    def test_strips_formatting(self):
        result = validate_imei("49-0154-2032375-18")
        assert result.is_valid


class TestCrossReferenceCheck:
    def test_matching_identifiers_clean(self):
        result = cross_reference_check(
            serial="C8QH6T96DPNG",
            model_number="A2483",  # iPhone 13 Pro US
            product_type="iPhone14,2",  # iPhone 13 Pro
        )
        assert not result.is_suspicious
        assert "No anomalies" in result.flags[0]

    def test_mismatched_model_vs_product_type(self):
        result = cross_reference_check(
            serial="C8QH6T96DPNG",
            model_number="A2341",  # iPhone 12 Pro
            product_type="iPhone12,3",  # iPhone 11 Pro
        )
        assert result.is_suspicious
        assert any("board swap" in f.lower() for f in result.flags)

    def test_invalid_imei_flagged(self):
        result = cross_reference_check(
            serial="C8QH6T96DPNG",
            model_number="A2483",
            product_type="iPhone14,2",
            imei="000000000000001",  # invalid Luhn
        )
        assert result.is_suspicious
        assert any("IMEI" in f for f in result.flags)

    def test_unknown_model_no_false_positive(self):
        result = cross_reference_check(
            serial="C8QH6T96DPNG",
            model_number="A9999",  # unknown
            product_type="iPhone99,1",  # unknown
        )
        assert not result.is_suspicious
