import os
from datetime import timedelta

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DISCOVERY_INTERVAL_SECONDS = max(
    60, int(os.getenv("DISCOVERY_INTERVAL_SECONDS", "120"))
)

celery_app = Celery(
    "ai_job_hunter",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    beat_schedule={
        "discover-jobs-on-schedule": {
            "task": "app.tasks.discover_jobs",
            "schedule": timedelta(seconds=DISCOVERY_INTERVAL_SECONDS),
        }
    },
)
