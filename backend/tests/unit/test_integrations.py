import httpx
import pytest

from app.services.integrations.agristack import AgriStackAdapter
from app.services.integrations.http import IntegrationUnavailable, request_json
from app.services.integrations.nasa_smap import NASASMAPAdapter
from app.services.integrations.ocr_service import SoilCardOCRAdapter
from app.services.integrations.sentinel2 import Sentinel2Adapter
from app.services.integrations.weather_api import OpenMeteoAdapter
from app.services.messaging import sms_gateway, whatsapp_gateway
from app.services.speech.bhashini_adapter import BhashiniAdapter
from config.settings import Settings


async def no_wait(_delay):
    return None


@pytest.mark.asyncio
async def test_request_json_retries_transient_http_failure():
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"error": "temporary"})
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await request_json("GET", "https://provider.test/data", client=client,
                                    attempts=2, backoff=0, sleep=no_wait)
    assert result == {"ok": True}
    assert calls == 2


@pytest.mark.asyncio
async def test_request_json_does_not_retry_bad_request():
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"error": "bad request"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(IntegrationUnavailable, match="HTTP 400"):
            await request_json("GET", "https://provider.test/data", client=client,
                               attempts=3, backoff=0, sleep=no_wait)
    assert calls == 1


@pytest.mark.asyncio
async def test_bhashini_speech_to_text_payload_and_retry():
    calls = {"config": 0, "inference": 0}

    def handler(request):
        if request.url.path.endswith("getModelsPipeline"):
            calls["config"] += 1
            assert request.headers["userID"] == "user-123"
            assert request.headers["ulcaApiKey"] == "secret"
            assert b'"taskType":["asr"]' in request.content
            if calls["config"] == 1:
                return httpx.Response(429, json={"error": "busy"}, headers={"Retry-After": "0"})
            return httpx.Response(200, json={
                "pipelineInferenceAPIEndPoint": {"callbackURL": "https://bhashini.test/infer",
                                                  "inferenceApiKey": {"name": "Authorization", "value": "infer-secret"}},
                "pipelineResponse": [{"taskType": "asr", "config": {"serviceId": "asr-hi-v1"}}],
            })
        assert request.headers["Authorization"] == "infer-secret"
        assert b"audioContent" in request.content and b"asr-hi-v1" in request.content
        calls["inference"] += 1
        if calls["inference"] == 1:
            return httpx.Response(429, json={"error": "busy"}, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"pipelineResponse": [{"taskType": "asr"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = BhashiniAdapter(client=client, user_id="user-123", api_key="secret",
                                  endpoint="https://bhashini.test/getModelsPipeline",
                                  pipeline_id="pipeline-v1", attempts=2, backoff=0)
        result = await adapter.speech_to_text(b"audio", "hi")
    assert result["pipelineResponse"][0]["taskType"] == "asr"
    assert calls == {"config": 2, "inference": 2}


@pytest.mark.asyncio
async def test_nasa_smap_surfaces_final_upstream_failure():
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(503, json={"error": "offline"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = NASASMAPAdapter(client=client, url="https://nasa.test/api/", username="user",
                                  password="password", attempts=2, backoff=0)
        with pytest.raises(IntegrationUnavailable):
            await adapter.fetch(bbox=(1, 2, 3, 4), start_date="2026-01-01", end_date="2026-01-02")
    assert calls == 2


@pytest.mark.asyncio
async def test_nasa_smap_appeears_auth_task_poll_and_quality_aware_csv():
    calls = {"login": 0, "submit": 0, "poll": 0}
    csv_body = (
        "Date,Latitude,Longitude,Category,SPL3SMP_E_006_Soil_Moisture_Retrieval_Data_AM_soil_moisture,"
        "SPL3SMP_E_006_Soil_Moisture_Retrieval_Data_AM_retrieval_qual_flag,"
        "SPL3SMP_E_006_Soil_Moisture_Retrieval_Data_PM_soil_moisture_pm,"
        "SPL3SMP_E_006_Soil_Moisture_Retrieval_Data_PM_retrieval_qual_flag_pm\n"
        "2026-10-28,12.9,77.5,plot,0.25,0,0.31,8\n"
        "2026-10-29,12.9,77.5,plot,-9999,65534,-9999,65534\n"
    )

    def handler(request):
        if request.url.path.endswith("/login"):
            calls["login"] += 1
            assert request.headers["Authorization"].startswith("Basic ")
            return httpx.Response(200, json={"token": "appeears-access-token"})
        assert request.headers["Authorization"] == "Bearer appeears-access-token"
        if request.url.path.endswith("/task"):
            calls["submit"] += 1
            body = request.read().decode()
            assert '"product":"SPL3SMP_E.006"' in body
            assert "soil_moisture_am" not in body
            assert '"startDate":"10-28-2026"' in body
            return httpx.Response(200, json={"task_id": "task-123"})
        if request.url.path.endswith("/task/task-123"):
            calls["poll"] += 1
            return httpx.Response(200, json={"status": "running" if calls["poll"] == 1 else "done"})
        if request.url.path.endswith("/bundle/task-123"):
            return httpx.Response(200, json={"files": [{"file_id": "file-1", "file_name": "SPL3SMP_E-006-results.csv"}]})
        if request.url.path.endswith("/bundle/task-123/file-1"):
            return httpx.Response(200, text=csv_body)
        raise AssertionError(f"Unexpected AppEEARS request: {request.url}")

    async def no_wait(_delay):
        return None

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = NASASMAPAdapter(client=client, url="https://appeears.test/api/", username="edl-user",
                                  password="edl-password", attempts=1, poll_interval=1,
                                  max_wait_seconds=10, sleep=no_wait)
        result = await adapter.fetch_point(latitude=12.9, longitude=77.5, start_date="2026-10-28",
                                          end_date="2026-10-29", plot_id=41)
    assert calls == {"login": 1, "submit": 1, "poll": 2}
    assert result["provider"] == "NASA AppEEARS"
    assert result["product_doi"] == "10.5067/M20OXIZHY3RJ"
    assert result["observations"][0]["soil_moisture_am"] == 0.25
    assert result["observations"][0]["quality_am"] == "recommended"
    assert result["observations"][0]["quality_pm"] == "recommended"
    assert result["observations"][1]["soil_moisture_am"] is None
    assert result["observations"][1]["quality_am"] == "unavailable"


@pytest.mark.asyncio
async def test_sentinel2_oauth_then_process_query():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        return httpx.Response(200, json={"ndvi": 0.7})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = Sentinel2Adapter(client=client, process_url="https://sentinel.test/process",
                                   token_url="https://sentinel.test/token", client_id="id",
                                   client_secret="secret", attempts=1)
        result = await adapter.fetch_indices(geometry={"type": "Point", "coordinates": [0, 0]},
                                             start_date="2026-01-01T00:00:00Z",
                                             end_date="2026-01-02T00:00:00Z", evalscript="//VERSION=3")
    assert result == {"ndvi": 0.7}
    assert requests[1].headers["Authorization"] == "Bearer token"


@pytest.mark.asyncio
async def test_agristack_requires_consent_and_returns_upstream_error():
    async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda _request: httpx.Response(401, json={"error": "invalid"}))) as client:
        adapter = AgriStackAdapter(client=client, base_url="https://agri.test", token_url="https://agri.test/token",
                                   client_id="id", client_secret="secret", attempts=1)
        with pytest.raises(IntegrationUnavailable):
            await adapter.prefill_plots("farmer", "consent")


@pytest.mark.asyncio
async def test_ocr_validates_soil_card_metrics_and_handles_provider_failure():
    async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"metrics": {"N_val": 120, "P_val": 20, "K_val": 40, "pH": 6.5}}))) as client:
        result = await SoilCardOCRAdapter(client=client, url="https://ocr.test", attempts=1).extract_metrics(b"image")
    assert result.n_val == 120 and result.ph == 6.5

    async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda _request: httpx.Response(502, json={"error": "down"}))) as client:
        with pytest.raises(IntegrationUnavailable):
            await SoilCardOCRAdapter(client=client, url="https://ocr.test", attempts=1).extract_metrics(b"image")


@pytest.mark.asyncio
async def test_sms_and_whatsapp_adapters_report_provider_failures(monkeypatch):
    monkeypatch.setattr(sms_gateway, "settings", Settings(sms_gateway_url="https://sms.test",
                                                           sms_gateway_api_key="key"))
    monkeypatch.setattr(whatsapp_gateway, "settings", Settings(whatsapp_gateway_url="https://wa.test",
                                                                 whatsapp_gateway_api_key="key"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda _request: httpx.Response(502, json={"error": "down"}))) as client:
        with pytest.raises(sms_gateway.SMSDeliveryUnavailable):
            await sms_gateway.send_otp_sms("+911234567890", "1234", client=client, attempts=1)
        with pytest.raises(whatsapp_gateway.WhatsAppDeliveryUnavailable):
            await whatsapp_gateway.send_message("+911234567890", "Alert", client=client, attempts=1)


@pytest.mark.asyncio
async def test_open_meteo_numeric_forecast_contract_and_sms_whatsapp_success_payloads(monkeypatch):
    captured = {}

    def weather_handler(request):
        captured["weather_url"] = str(request.url)
        return httpx.Response(200, json={
            "current_units": {"time": "iso8601", "precipitation": "mm", "temperature_2m": "°C",
                              "relative_humidity_2m": "%", "wind_speed_10m": "m/s"},
            "current": {"time": "2026-10-30T12:00", "precipitation": 0.2,
                        "temperature_2m": 22.5, "relative_humidity_2m": 65, "wind_speed_10m": 3.1},
            "hourly_units": {"time": "iso8601", "precipitation": "mm", "temperature_2m": "°C",
                             "relative_humidity_2m": "%", "wind_speed_10m": "m/s",
                             "et0_fao_evapotranspiration": "mm"},
            "hourly": {"time": ["2026-10-30T12:00", "2026-10-30T13:00"],
                       "precipitation": [0.2, 1.5], "temperature_2m": [22.5, 22],
                       "relative_humidity_2m": [65, 68], "et0_fao_evapotranspiration": [0.1, 0.12],
                       "wind_speed_10m": [3.1, 4]},
            "daily_units": {"time": "iso8601", "precipitation_sum": "mm", "uv_index_max": "index"},
            "daily": {"time": ["2026-10-30"], "precipitation_sum": [4.2], "uv_index_max": [7.1]},
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(weather_handler)) as client:
        data = await OpenMeteoAdapter(client=client, url="https://weather.test/forecast", attempts=1).forecast(12.9, 77.5)
    assert data["forecast"][0]["rainfall_mm"] == 0.2
    assert data["forecast"][1]["rainfall_mm"] == 1.5
    assert data["units"] == {"rainfall": "mm", "temperature": "C", "wind_speed": "m/s"}
    assert data["current"]["wind_speed_m_s"] == 3.1
    assert data["hourly_data"][1]["relative_humidity_2m"] == 68
    assert data["hourly_data"][1]["et0_fao_evapotranspiration"] == 0.12
    assert data["daily_data"][0]["uv_index_max"] == 7.1
    assert data["daily_data"][0]["date"] == "2026-10-30"
    assert "soil_moisture_0_to_1cm" in captured["weather_url"]
    assert "daily=weather_code" in captured["weather_url"]
    assert "%2C" not in captured["weather_url"]
    assert "latitude=12.9" in captured["weather_url"] and "longitude=77.5" in captured["weather_url"]
    monkeypatch.setattr(sms_gateway, "settings", Settings(sms_gateway_url="https://sms.test/send",
                                                            sms_gateway_api_key="sms-secret", sms_sender_id="FIELD"))
    monkeypatch.setattr(whatsapp_gateway, "settings", Settings(whatsapp_gateway_url="https://wa.test/send",
                                                                 whatsapp_gateway_api_key="wa-secret", whatsapp_sender_id="FIELD-WA"))
    requests = []

    def messaging_handler(request):
        requests.append((request.url.host, request.headers.get("Authorization"), request.read()))
        return httpx.Response(200, json={"message_id": "provider-message-1"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(messaging_handler)) as client:
        await sms_gateway.send_sms_message("+14155550123", "test", client=client, attempts=1)
        result = await whatsapp_gateway.send_message("+14155550123", "test", client=client,
                                                     template="alert-v1", variables={"crop": "Ragi"}, attempts=1)
    assert requests[0][0] == "sms.test" and requests[0][1] == "Bearer sms-secret"
    assert b"FIELD" in requests[0][2] and b"test" in requests[0][2]
    assert requests[1][0] == "wa.test" and requests[1][1] == "Bearer wa-secret"
    assert b"alert-v1" in requests[1][2] and b"Ragi" in requests[1][2]
    assert result["message_id"] == "provider-message-1"
