import asyncio

from app.celery_app import celery_app
from app.discovery_service import run_discovery_cycle


@celery_app.task(
    name="app.tasks.discover_jobs",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def discover_jobs(self):
    try:
        return asyncio.run(run_discovery_cycle())
    except Exception as exc:
        raise self.retry(exc=exc)
