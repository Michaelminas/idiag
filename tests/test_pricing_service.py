"""Tests for market pricing service."""

from unittest.mock import patch

import pytest

from app.services.pricing_service import (
    _grade_to_condition,
    _parse_swappa_html,
    lookup_price,
)


class TestGradeToCondition:
    def test_grade_a_maps_to_good(self):
        assert _grade_to_condition("A") == "good"

    def test_grade_b_maps_to_good(self):
        assert _grade_to_condition("B") == "good"

    def test_grade_c_maps_to_fair(self):
        assert _grade_to_condition("C") == "fair"

    def test_grade_d_maps_to_poor(self):
        assert _grade_to_condition("D") == "poor"

    def test_empty_grade_maps_to_poor(self):
        assert _grade_to_condition("") == "poor"


class TestParseSwappaHtml:
    def test_returns_none_for_empty_html(self):
        assert _parse_swappa_html("") is None

    def test_returns_none_for_no_prices(self):
        assert _parse_swappa_html("<html><body>No phone data</body></html>") is None

    def test_extracts_prices_near_storage_labels(self):
        # Spacing must exceed the 500-char context window between storage sections
        padding = " " * 600
        html = (
            '<div class="variant">128GB '
            '<span>$450</span> <span>$380</span> <span>$300</span>'
            '</div>'
            + padding
            + '<div class="variant">256GB '
            '<span>$520</span> <span>$440</span> <span>$360</span>'
            '</div>'
        )
        result = _parse_swappa_html(html)
        assert result is not None
        assert "128" in result
        assert "256" in result
        assert result["128"]["good"] == 450
        assert result["128"]["poor"] == 300


class TestLookupPrice:
    def test_static_fallback_for_known_model(self):
        result = lookup_price("iPhone 13 Pro")
        assert result["source"] == "static"
        assert result["model"] == "iPhone 13 Pro"
        assert "128" in result["prices"]

    def test_static_with_storage_and_grade(self):
        result = lookup_price("iPhone 13 Pro", storage_gb=128, grade="B")
        assert result["suggested_price"] is not None
        assert result["suggested_price"] > 0

    def test_unknown_model_returns_no_data(self):
        result = lookup_price("Samsung Galaxy S99")
        assert result["source"] == "none"
        assert result["prices"] == {}
        assert result["suggested_price"] is None

    def test_suggested_price_none_without_storage(self):
        result = lookup_price("iPhone 13 Pro", storage_gb=0)
        assert result["suggested_price"] is None

    def test_suggested_price_none_for_unknown_storage(self):
        result = lookup_price("iPhone 13 Pro", storage_gb=2048)
        assert result["suggested_price"] is None

    @patch("app.services.pricing_service._scrape_swappa")
    def test_swappa_result_used_when_available(self, mock_scrape):
        mock_scrape.return_value = {
            "128": {"good": 999, "fair": 888, "poor": 777},
        }
        # Clear cache for this test
        from app.services.pricing_service import _cache
        _cache.pop("apple-iphone-13-pro", None)

        result = lookup_price("iPhone 13 Pro", storage_gb=128, grade="A")
        assert result["source"] == "swappa"
        assert result["suggested_price"] == 999

    @patch("app.services.pricing_service._scrape_swappa", return_value=None)
    def test_falls_back_to_static_when_scrape_fails(self, _mock):
        from app.services.pricing_service import _cache
        _cache.pop("apple-iphone-14", None)

        result = lookup_price("iPhone 14", storage_gb=128, grade="B")
        assert result["source"] == "static"
        assert result["suggested_price"] is not None


class TestPricingAPI:
    def test_lookup_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)

        resp = client.get("/api/pricing/lookup?model=iPhone+13+Pro&storage_gb=128&grade=B")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "iPhone 13 Pro"
        assert data["suggested_price"] is not None

    def test_lookup_unknown_model(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)

        resp = client.get("/api/pricing/lookup?model=Unknown+Phone")
        assert resp.status_code == 200
        assert resp.json()["source"] == "none"
