"""Preference-aware, deduplicated alert delivery with receipts and dead letters."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from celery.utils.log import get_task_logger
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError

from app.models.alert import Alert
from app.models.farmer import Farmer
from app.models.farmer_preferences import FarmerPreferences
from app.services.messaging.sms_gateway import send_sms_message
from app.services.messaging.whatsapp_gateway import send_message
from app.workers.celery_app import celery_app
from app.workers.tasks.common import WorkerSession, run_async
from config.settings import settings

logger = get_task_logger(__name__)
REMINDER_TYPES = ("sowing_reminder", "fertilizer_reminder", "sowing_window_compressed")
TEMPLATES = {
    "sowing_reminder": {
        "en": "A planned sowing date is due. Check local weather and field conditions before sowing.",
        "hi": "बुवाई की नियोजित तारीख आ गई है। बुवाई से पहले स्थानीय मौसम और खेत की स्थिति देखें।",
        "kn": "ಯೋಜಿತ ಬಿತ್ತನೆ ದಿನಾಂಕ ಬಂದಿದೆ. ಬಿತ್ತನೆಗೂ ಮೊದಲು ಸ್ಥಳೀಯ ಹವಾಮಾನ ಮತ್ತು ಹೊಲದ ಸ್ಥಿತಿಯನ್ನು ಪರಿಶೀಲಿಸಿ.",
    },
    "fertilizer_reminder": {
        "en": "A planned fertilizer application is due. Follow your soil test and product instructions.",
        "hi": "उर्वरक देने का नियोजित समय है। मिट्टी परीक्षण और उत्पाद निर्देशों का पालन करें।",
        "kn": "ಯೋಜಿತ ಗೊಬ್ಬರ ಹಾಕುವ ಸಮಯ ಬಂದಿದೆ. ಮಣ್ಣಿನ ಪರೀಕ್ಷೆ ಮತ್ತು ಉತ್ಪನ್ನದ ಸೂಚನೆಗಳನ್ನು ಅನುಸರಿಸಿ.",
    },
    "sowing_window_compressed": {
        "en": "The approved sowing window for {crop_name} closes in about {days_remaining} day(s). Check local field conditions.",
        "hi": "{crop_name} की स्वीकृत बुवाई अवधि लगभग {days_remaining} दिन में समाप्त होगी। खेत की स्थिति जांचें।",
        "kn": "{crop_name} ಬೆಳೆಯ ಅನುಮೋದಿತ ಬಿತ್ತನೆ ಅವಧಿ ಸುಮಾರು {days_remaining} ದಿನಗಳಲ್ಲಿ ಮುಗಿಯುತ್ತದೆ. ಹೊಲದ ಸ್ಥಿತಿ ಪರಿಶೀಲಿಸಿ.",
    },
}


def is_due(payload: dict, now: datetime | None = None) -> bool:
    value = payload.get("due_at") or payload.get("scheduled_for")
    if not value:
        return payload.get("template_key") == "sowing_window_compressed"
    try:
        due_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return False
    if due_at.tzinfo is None:
        return False
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return due_at <= current


def _quiet_until(preferences: FarmerPreferences, now: datetime) -> datetime | None:
    start, end = preferences.quiet_hours_start, preferences.quiet_hours_end
    if start is None or end is None:
        return None
    local = now.astimezone(ZoneInfo(preferences.timezone))
    current_time = local.timetz().replace(tzinfo=None)
    if start < end:
        quiet = start <= current_time < end
        end_day = local.date()
    else:
        quiet = current_time >= start or current_time < end
        end_day = local.date() + (timedelta(days=1) if current_time >= start else timedelta(days=0))
    if not quiet:
        return None
    return datetime.combine(end_day, end, tzinfo=local.tzinfo).astimezone(UTC)


def _message(alert: Alert, farmer: Farmer, preferences: FarmerPreferences) -> tuple[str, str]:
    language = (preferences.language or farmer.language or "en").split("-")[0].lower()
    if language not in {"en", "hi", "kn"}:
        language = "en"
    template_key = alert.payload.get("template_key", alert.alert_type)
    template = TEMPLATES.get(template_key, {})
    text = template.get(language) or template.get("en")
    if text is None:
        text = alert.payload.get("message") or "You have a Field Shift reminder."
    return text.format(**alert.payload), language


async def _attempt_channel(alert: Alert, channel: str, phone: str, message: str) -> dict:
    try:
        if channel == "sms":
            await send_sms_message(phone, message)
            provider_reference = None
        else:
            response = await send_message(phone, message)
            provider_reference = (response.get("message_id") or response.get("id")) if isinstance(response, dict) else None
        return {"status": "sent", "at": datetime.now(UTC).isoformat(), "provider_reference": provider_reference}
    except Exception as exc:
        logger.warning("Alert delivery failed alert_id=%s channel=%s error_type=%s", alert.id, channel, type(exc).__name__)
        return {"status": "failed", "at": datetime.now(UTC).isoformat(), "error_code": type(exc).__name__[:64]}


async def _dispatch_due_reminders(now: datetime | None = None) -> dict:
    current = now or datetime.now(UTC)
    sent = failed = skipped = dead_lettered = suppressed = 0
    async with WorkerSession() as session:
        rows = (await session.execute(
            select(Alert, Farmer, FarmerPreferences)
            .join(Farmer, Farmer.id == Alert.farmer_id)
            .outerjoin(FarmerPreferences, FarmerPreferences.farmer_id == Farmer.id)
            .where(Alert.status.in_(("pending", "retry")), Alert.alert_type.in_(REMINDER_TYPES),
                   or_(Alert.next_attempt_at.is_(None), Alert.next_attempt_at <= current))
            .order_by(Alert.created_at, Alert.id).limit(500).with_for_update(of=Alert, skip_locked=True)
        )).all()
        for alert, farmer, preferences in rows:
            if not is_due(alert.payload, current):
                skipped += 1
                continue
            enabled = preferences and (
                preferences.weather_alerts_enabled if alert.alert_type == "sowing_window_compressed"
                else preferences.reminders_enabled
            )
            if not enabled:
                alert.status = "suppressed"
                alert.delivery_receipts = {**(alert.delivery_receipts or {}), "suppressed": {
                    "reason": "user_opt_out", "at": current.isoformat(),
                }}
                suppressed += 1
                await session.commit()
                continue
            quiet_until = _quiet_until(preferences, current)
            if quiet_until:
                alert.next_attempt_at = quiet_until
                skipped += 1
                await session.commit()
                continue
            channels = []
            if preferences.sms_enabled and settings.reminder_sms_enabled:
                channels.append("sms")
            if preferences.whatsapp_enabled and settings.reminder_whatsapp_enabled:
                channels.append("whatsapp")
            if not channels:
                alert.status = "suppressed"
                alert.delivery_receipts = {**(alert.delivery_receipts or {}), "suppressed": {
                    "reason": "no_delivery_channel_opted_in", "at": current.isoformat(),
                }}
                suppressed += 1
                await session.commit()
                continue

            message, language = _message(alert, farmer, preferences)
            receipts = dict(alert.delivery_receipts or {})
            for channel in channels:
                if receipts.get(channel, {}).get("status") == "sent":
                    continue
                prior_attempts = list(receipts.get(channel, {}).get("attempts", []))
                result = await _attempt_channel(alert, channel, farmer.phone, message)
                prior_attempts.append(result)
                receipts[channel] = {"status": result["status"], "attempts": prior_attempts}
            receipts["language"] = language
            alert.delivery_receipts = receipts
            if all(receipts.get(channel, {}).get("status") == "sent" for channel in channels):
                alert.status = "sent"
                alert.next_attempt_at = None
                sent += 1
            else:
                alert.attempt_count += 1
                failed += 1
                if alert.attempt_count >= settings.alert_max_attempts:
                    alert.status = "dead_letter"
                    alert.dead_lettered_at = current
                    alert.next_attempt_at = None
                    dead_lettered += 1
                else:
                    alert.status = "retry"
                    delay = settings.alert_retry_base_seconds * (2 ** (alert.attempt_count - 1))
                    alert.next_attempt_at = current + timedelta(seconds=delay)
                alert.last_error_code = "delivery_failed"
            await session.commit()
    return {"sent": sent, "failed": failed, "skipped": skipped,
            "suppressed": suppressed, "dead_lettered": dead_lettered}


@celery_app.task(name="field_shift.dispatch_reminders", autoretry_for=(SQLAlchemyError,),
                 retry_backoff=True, retry_kwargs={"max_retries": 3})
def dispatch_reminders() -> dict:
    return run_async(_dispatch_due_reminders())
