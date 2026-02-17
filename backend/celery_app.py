"""Celery application configuration.

Uses Redis as broker when configured, falls back to memory:// for local dev/tests.
"""

from celery import Celery
from celery.schedules import crontab

from backend.config.settings import get_settings

settings = get_settings()

app = Celery("dealhawk")

app.conf.update(
    broker_url=settings.effective_celery_broker,
    result_backend=settings.effective_celery_backend,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "refresh-market-cache": {
            "task": "backend.tasks.market_tasks.refresh_market_cache",
            "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
        },
    },
)

app.autodiscover_tasks(["backend.tasks"])
