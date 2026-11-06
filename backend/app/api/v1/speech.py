"""Authenticated speech and translation proxies backed by Bhashini."""

import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_farmer
from app.models.farmer import Farmer
from app.schemas.speech import SpeechToTextRequest, TextToSpeechRequest, TranslationRequest
from app.services.integrations.http import IntegrationUnavailable
from app.services.speech.bhashini_adapter import BhashiniAdapter

router = APIRouter(prefix="/speech", tags=["speech"])


@router.post("/stt")
async def speech_to_text(payload: SpeechToTextRequest, _: Farmer = Depends(get_current_farmer)) -> dict:
    try:
        audio = base64.b64decode(payload.audio_content, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="audio_content must be valid base64") from exc
    try:
        return await BhashiniAdapter().speech_to_text(
            audio, payload.language, audio_format=payload.audio_format, sampling_rate=payload.sampling_rate
        )
    except IntegrationUnavailable as exc:
        raise HTTPException(status_code=502, detail="Speech provider is unavailable") from exc


@router.post("/tts")
async def text_to_speech(payload: TextToSpeechRequest, _: Farmer = Depends(get_current_farmer)) -> dict:
    try:
        return await BhashiniAdapter().text_to_speech(payload.text, payload.language)
    except IntegrationUnavailable as exc:
        raise HTTPException(status_code=502, detail="Speech provider is unavailable") from exc


@router.post("/translate")
async def translate(payload: TranslationRequest, _: Farmer = Depends(get_current_farmer)) -> dict:
    try:
        return await BhashiniAdapter().translate(payload.text, payload.source_language, payload.target_language)
    except IntegrationUnavailable as exc:
        raise HTTPException(status_code=502, detail="Speech provider is unavailable") from exc
