from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_farmer
from app.api.v1 import speech
from app.main import app
from app.services.integrations.http import IntegrationUnavailable


class FakeBhashini:
    async def speech_to_text(self, audio, language, **kwargs):
        return {"transcript": audio.decode(), "language": language, "format": kwargs["audio_format"]}

    async def text_to_speech(self, text, language):
        return {"audioContent": "encoded-audio", "language": language, "text": text}

    async def translate(self, text, source_language, target_language):
        return {"text": text, "source": source_language, "target": target_language}


@pytest.fixture
def authenticated_speech_app(monkeypatch):
    monkeypatch.setattr(speech, "BhashiniAdapter", FakeBhashini)
    app.dependency_overrides[get_current_farmer] = lambda: SimpleNamespace(id=1)
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_bhashini_proxy_routes_dispatch_stt_tts_and_translation(authenticated_speech_app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        stt = await client.post("/api/v1/speech/stt", json={
            "audio_content": "SGVsbG8=", "language": "en", "audio_format": "wav",
        })
        tts = await client.post("/api/v1/speech/tts", json={"text": "hello", "language": "en"})
        translated = await client.post("/api/v1/speech/translate", json={
            "text": "hello", "source_language": "en", "target_language": "hi",
        })
    assert stt.status_code == 200 and stt.json()["transcript"] == "Hello"
    assert tts.status_code == 200 and tts.json()["audioContent"] == "encoded-audio"
    assert translated.status_code == 200 and translated.json()["target"] == "hi"


@pytest.mark.asyncio
async def test_speech_proxy_rejects_bad_base64_and_maps_provider_failure(authenticated_speech_app, monkeypatch):
    async def provider_failure(*_args, **_kwargs):
        raise IntegrationUnavailable("upstream is down")

    monkeypatch.setattr(FakeBhashini, "speech_to_text", provider_failure)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bad_payload = await client.post("/api/v1/speech/stt", json={"audio_content": "%%%", "language": "en"})
        failed_provider = await client.post("/api/v1/speech/stt", json={"audio_content": "YQ==", "language": "en"})
    assert bad_payload.status_code == 422
    assert failed_provider.status_code == 502
