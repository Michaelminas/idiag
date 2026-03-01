"""Tests for verification service with mocked HTTP and device layer."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.verification_service import _parse_sickw_result, check_imei_sickw


class TestParseSickwResult:
    def test_clean_result(self):
        raw = {
            "result": {
                "Blacklist Status": "Clean",
                "iCloud Lock": "OFF",
                "Carrier": "T-Mobile USA",
                "SIM-Lock Status": "Unlocked",
            }
        }
        result = _parse_sickw_result(raw)
        assert result.blacklist_status == "clean"
        assert result.fmi_status == "off"
        assert result.carrier == "T-Mobile USA"
        assert not result.carrier_locked

    def test_blacklisted_result(self):
        raw = {
            "result": {
                "Blacklist Status": "Blacklisted - Lost/Stolen",
                "iCloud Lock": "ON",
                "Carrier": "AT&T",
                "SIM-Lock Status": "Locked",
            }
        }
        result = _parse_sickw_result(raw)
        assert result.blacklist_status == "blacklisted"
        assert result.fmi_status == "on"
        assert result.carrier_locked

    def test_non_dict_result(self):
        raw = {"result": "Some error string"}
        result = _parse_sickw_result(raw)
        assert result.blacklist_status == "unknown"


class TestCheckImeiSickw:
    @pytest.mark.asyncio
    async def test_no_api_key_returns_error(self):
        with patch("app.services.verification_service.settings") as mock_settings:
            mock_settings.sickw_api_key = ""
            result = await check_imei_sickw("353462111234567")
            assert "error" in result

    @pytest.mark.asyncio
    async def test_successful_api_call(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "Blacklist Status": "Clean",
                "iCloud Lock": "OFF",
                "Carrier": "Verizon",
                "SIM-Lock Status": "Unlocked",
            }
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.verification_service.settings") as mock_settings:
            mock_settings.sickw_api_key = "test-key"
            mock_settings.sickw_base_url = "https://sickw.com/api.php"
            mock_settings.sickw_default_service = 61
            with patch(
                "app.services.verification_service.httpx.AsyncClient",
                return_value=mock_client,
            ):
                result = await check_imei_sickw("353462111234567")
        assert "error" not in result
        assert result["result"]["Carrier"] == "Verizon"
