"""Retrying JSON adapter for an SMS gateway."""

import httpx

from app.services.integrations.http import IntegrationUnavailable, request_json
from config.settings import settings


class SMSDeliveryUnavailable(IntegrationUnavailable):
    pass


async def send_otp_sms(phone: str, otp: str, *, client: httpx.AsyncClient | None = None,
                       attempts: int = 3, backoff: float = 0.2) -> None:
    await send_sms_message(phone, f"Your Field Shift verification code is {otp}.",
                           client=client, attempts=attempts, backoff=backoff)


async def send_sms_message(phone: str, message: str, *, client: httpx.AsyncClient | None = None,
                           attempts: int = 3, backoff: float = 0.2) -> None:
    if not settings.sms_gateway_url or not settings.sms_gateway_api_key:
        raise SMSDeliveryUnavailable("SMS gateway is not configured")
    headers = {"Authorization": f"Bearer {settings.sms_gateway_api_key.get_secret_value()}"}
    payload = {"to": phone, "message": message}
    if settings.sms_sender_id:
        payload["sender_id"] = settings.sms_sender_id
    try:
        await request_json("POST", settings.sms_gateway_url, client=client, attempts=attempts,
                           backoff=backoff, headers=headers, json=payload)
    except IntegrationUnavailable as exc:
        raise SMSDeliveryUnavailable("SMS provider is unavailable") from exc
