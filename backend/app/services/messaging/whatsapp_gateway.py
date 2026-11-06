"""Configurable WhatsApp business messaging gateway adapter."""

import httpx

from app.services.integrations.http import IntegrationUnavailable, request_json
from config.settings import settings


class WhatsAppDeliveryUnavailable(IntegrationUnavailable):
    pass


async def send_message(phone: str, message: str, *, template: str | None = None,
                       variables: dict | None = None, client: httpx.AsyncClient | None = None,
                       attempts: int = 3, backoff: float = 0.2) -> dict | list:
    if not settings.whatsapp_gateway_url or not settings.whatsapp_gateway_api_key:
        raise WhatsAppDeliveryUnavailable("WhatsApp gateway is not configured")
    payload = {"to": phone, "message": message}
    if template:
        payload["template"] = template
    if variables:
        payload["variables"] = variables
    if settings.whatsapp_sender_id:
        payload["sender_id"] = settings.whatsapp_sender_id
    try:
        return await request_json("POST", settings.whatsapp_gateway_url, client=client,
                                  attempts=attempts, backoff=backoff,
                                  headers={"Authorization": f"Bearer {settings.whatsapp_gateway_api_key.get_secret_value()}"},
                                  json=payload)
    except IntegrationUnavailable as exc:
        raise WhatsAppDeliveryUnavailable("WhatsApp provider is unavailable") from exc
