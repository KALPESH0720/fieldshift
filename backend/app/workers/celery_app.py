"""Celery application and periodic job schedule for Field Shift."""

from celery import Celery
from celery.schedules import crontab

from config.settings import settings

celery_app = Celery(
    "field_shift",
    broker=settings.redis_url,
    include=[
        "app.workers.tasks.price_ingestion",
        "app.workers.tasks.weather_alerts",
        "app.workers.tasks.reminders",
        "app.workers.tasks.soil_cards",
        "app.workers.tasks.satellite_monitoring",
    ],
)
celery_app.conf.update(
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "daily-agmarknet-price-ingestion": {
            "task": "field_shift.ingest_daily_prices",
            "schedule": crontab(hour=2, minute=30),
        },
        "hourly-weather-sowing-window-alerts": {
            "task": "field_shift.poll_weather_alerts",
            "schedule": crontab(minute=0),
        },
        "hourly-sowing-and-fertilizer-reminders": {
            "task": "field_shift.dispatch_reminders",
            "schedule": crontab(minute=15),
        },
        "daily-soil-card-photo-retention": {
            "task": "field_shift.purge_expired_soil_cards",
            "schedule": crontab(hour=3, minute=10),
        },
    },
)

