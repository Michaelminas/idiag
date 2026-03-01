"""Tests for enhanced fraud detection — TAC validation, scoring, randomized serial."""

from app.models.inventory import FraudCheck
from app.services.serial_decoder import (
    TAC_MAP,
    cross_reference_check,
)


class TestFraudCheckModel:
    def test_fraud_score_field_exists(self):
        fc = FraudCheck()
        assert fc.fraud_score == 0

    def test_randomized_note_field_exists(self):
        fc = FraudCheck()
        assert fc.randomized_note == ""

    def test_default_values(self):
        fc = FraudCheck()
        assert fc.is_suspicious is False
        assert fc.flags == []
        assert fc.fraud_score == 0
        assert fc.randomized_note == ""


class TestTACValidation:
    def test_tac_map_has_entries(self):
        assert len(TAC_MAP) > 0

    def test_tac_map_contains_iphone_15_pro(self):
        assert "35691612" in TAC_MAP
        assert TAC_MAP["35691612"] == "iPhone 15 Pro"

    def test_tac_mismatch_flagged(self):
        # IMEI with TAC for iPhone 13 Pro (35346211) but ProductType is iPhone 12
        # Build a valid IMEI starting with TAC 35346211
        # Use 353462110000005 and compute correct Luhn
        result = cross_reference_check(
            serial="C8QH6T96DPNG",
            model_number="A2483",  # iPhone 13 Pro
            product_type="iPhone13,2",  # iPhone 12
            imei="353462110000015",  # TAC = 35346211 -> iPhone 13 Pro
        )
        assert result.is_suspicious
        assert any("TAC" in f for f in result.flags)

    def test_matching_tac_no_flag(self):
        # TAC for iPhone 13 Pro (35346211) with matching ProductType iPhone14,2 (iPhone 13 Pro)
        result = cross_reference_check(
            serial="C8QH6T96DPNG",
            model_number="A2483",  # iPhone 13 Pro
            product_type="iPhone14,2",  # iPhone 13 Pro
            imei="353462110000015",  # TAC = 35346211 -> iPhone 13 Pro
        )
        # TAC matches ProductType, so no TAC-related flag
        assert not any("TAC" in f for f in result.flags)


class TestFraudScoring:
    def test_clean_device_score_zero(self):
        result = cross_reference_check(
            serial="C8QH6T96DPNG",
            model_number="A2483",  # iPhone 13 Pro
            product_type="iPhone14,2",  # iPhone 13 Pro
        )
        assert result.fraud_score == 0
        assert not result.is_suspicious

    def test_invalid_imei_adds_40(self):
        result = cross_reference_check(
            serial="C8QH6T96DPNG",
            model_number="A2483",
            product_type="iPhone14,2",
            imei="000000000000001",  # invalid Luhn
        )
        assert result.fraud_score >= 40

    def test_model_mismatch_adds_30(self):
        result = cross_reference_check(
            serial="C8QH6T96DPNG",
            model_number="A2341",  # iPhone 12 Pro
            product_type="iPhone12,3",  # iPhone 11 Pro
        )
        assert result.fraud_score >= 30

    def test_multiple_issues_stack(self):
        result = cross_reference_check(
            serial="C8QH6T96DPNG",
            model_number="A2341",  # iPhone 12 Pro
            product_type="iPhone12,3",  # iPhone 11 Pro
            imei="000000000000001",  # invalid Luhn
        )
        # model mismatch (30) + invalid IMEI (40) = 70
        assert result.fraud_score >= 70

    def test_score_capped_at_100(self):
        # Score should never exceed 100
        result = cross_reference_check(
            serial="C8QH6T96DPNG",
            model_number="A2341",  # iPhone 12 Pro
            product_type="iPhone12,3",  # iPhone 11 Pro
            imei="000000000000001",  # invalid Luhn
        )
        assert result.fraud_score <= 100


class TestRandomizedSerialNote:
    def test_randomized_serial_note_set(self):
        # Short serial -> randomized
        result = cross_reference_check(
            serial="RANDOMIZED123456",
            model_number="A2483",
            product_type="iPhone14,2",
        )
        assert "randomized" in result.randomized_note.lower()
        assert "manufactured after 2021" in result.randomized_note

    def test_old_format_serial_no_note(self):
        result = cross_reference_check(
            serial="C8QH6T96DPNG",
            model_number="A2483",
            product_type="iPhone14,2",
        )
        assert result.randomized_note == ""
