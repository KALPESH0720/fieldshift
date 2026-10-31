"""Async adapter for Bhashini's pipeline inference endpoint."""

import base64

import httpx

from app.services.integrations.http import IntegrationUnavailable, request_json
from config.settings import settings


class BhashiniAdapter:
    def __init__(self, *, client: httpx.AsyncClient | None = None, api_key: str | None = None,
                 endpoint: str | None = None, user_id: str | None = None, pipeline_id: str | None = None,
                 asr_service_id: str | None = None, tts_service_id: str | None = None,
                 translation_service_id: str | None = None, attempts: int = 3, backoff: float = 0.2):
        self.client = client
        self.api_key = api_key or (settings.bhashini_api_key.get_secret_value() if settings.bhashini_api_key else None)
        self.user_id = user_id or settings.bhashini_user_id
        self.config_endpoint = endpoint or settings.bhashini_config_url
        self.pipeline_id = pipeline_id or settings.bhashini_pipeline_id
        self.asr_service_id = asr_service_id or settings.bhashini_asr_service_id
        self.tts_service_id = tts_service_id or settings.bhashini_tts_service_id
        self.translation_service_id = translation_service_id or settings.bhashini_translation_service_id
        self.attempts, self.backoff = attempts, backoff

    async def speech_to_text(self, audio: bytes, language: str, *, audio_format: str = "wav",
                             sampling_rate: int = 16000) -> dict:
        if not audio:
            raise ValueError("audio cannot be empty")
        task = self._task("asr", language, service_id=self.asr_service_id,
                          audioFormat=audio_format, samplingRate=sampling_rate)
        data = await self._infer([task], {"audio": [{"audioContent": base64.b64encode(audio).decode("ascii")}]})
        return data

    async def text_to_speech(self, text: str, language: str) -> dict:
        if not text.strip():
            raise ValueError("text cannot be empty")
        task = self._task("tts", language, service_id=self.tts_service_id)
        return await self._infer([task], {"input": [{"source": text}]})

    async def translate(self, text: str, source_language: str, target_language: str) -> dict:
        if not text.strip():
            raise ValueError("text cannot be empty")
        task = self._task("translation", source_language, target_language,
                          service_id=self.translation_service_id)
        return await self._infer([task], {"input": [{"source": text}]})

    async def _infer(self, tasks: list[dict], input_data: dict) -> dict:
        if not self.api_key or not self.user_id or not self.pipeline_id:
            raise IntegrationUnavailable("Bhashini ULCA user ID, API key, and pipeline ID are required")
        discovery_config = {key: value for key, value in tasks[0].get("config", {}).items()
                            if key != "serviceId"}
        config_payload = {
            "pipelineId": self.pipeline_id,
            "taskType": [task["taskType"] for task in tasks],
            "config": discovery_config,
        }
        config_result = await request_json(
            "POST", self.config_endpoint, client=self.client, attempts=self.attempts,
            backoff=self.backoff, headers={"userID": self.user_id, "ulcaApiKey": self.api_key},
            json=config_payload,
        )
        if not isinstance(config_result, dict):
            raise IntegrationUnavailable("Bhashini pipeline configuration returned an unexpected response")
        endpoint_config = config_result.get("pipelineInferenceAPIEndPoint") or {}
        compute_endpoint = endpoint_config.get("callbackURL")
        inference_key = endpoint_config.get("inferenceApiKey") or {}
        auth_name, auth_value = inference_key.get("name"), inference_key.get("value")
        pipeline_response = config_result.get("pipelineResponse") or []
        resolved_services = {
            item.get("taskType"): (item.get("config") or {}).get("serviceId")
            for item in pipeline_response if isinstance(item, dict)
        }
        if not compute_endpoint or not auth_name or not auth_value:
            raise IntegrationUnavailable("Bhashini pipeline configuration omitted inference credentials")
        for task in tasks:
            service_id = task.get("config", {}).get("serviceId") or resolved_services.get(task["taskType"])
            if service_id:
                task["config"]["serviceId"] = service_id
            else:
                raise IntegrationUnavailable("Bhashini pipeline configuration omitted a requested service ID")
        payload = {"pipelineTasks": tasks, "inputData": input_data}
        result = await request_json(
            "POST", compute_endpoint, client=self.client, attempts=self.attempts,
            backoff=self.backoff, headers={auth_name: auth_value}, json=payload,
        )
        if not isinstance(result, dict):
            raise IntegrationUnavailable("Bhashini returned an unexpected response")
        return result

    @staticmethod
    def _task(task_type: str, source: str, target: str | None = None,
              service_id: str | None = None, **options) -> dict:
        language = {"sourceLanguage": source}
        if target:
            language["targetLanguage"] = target
        config = {"language": language, **options}
        if service_id:
            config["serviceId"] = service_id
        return {"taskType": task_type, "config": config}


async def speech_to_text(audio: bytes, language: str, **kwargs) -> dict:
    return await BhashiniAdapter().speech_to_text(audio, language, **kwargs)


async def text_to_speech(text: str, language: str) -> dict:
    return await BhashiniAdapter().text_to_speech(text, language)


async def translate(text: str, source_language: str, target_language: str) -> dict:
    return await BhashiniAdapter().translate(text, source_language, target_language)
