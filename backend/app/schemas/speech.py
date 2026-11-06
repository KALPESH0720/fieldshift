"""Request contracts for authenticated Bhashini speech proxy endpoints."""

from pydantic import Field

from app.schemas.common import StrictSchema


class SpeechToTextRequest(StrictSchema):
    audio_content: str = Field(min_length=1)
    language: str = Field(min_length=2, max_length=16)
    audio_format: str = Field(default="wav", min_length=2, max_length=16)
    sampling_rate: int = Field(default=16000, gt=0, le=192000)


class TextToSpeechRequest(StrictSchema):
    text: str = Field(min_length=1, max_length=10000)
    language: str = Field(min_length=2, max_length=16)


class TranslationRequest(StrictSchema):
    text: str = Field(min_length=1, max_length=10000)
    source_language: str = Field(min_length=2, max_length=16)
    target_language: str = Field(min_length=2, max_length=16)
