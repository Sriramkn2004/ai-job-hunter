import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.discovery import discover_all_with_report
from app.models import BoardSourceRecord, BoardSourceHealthRecord, JobRecord, NotificationRecord, PreferencesRecord
from app.schemas import BoardSource, Preferences
from app.notifications import build_job_alert, send_telegram_message


def deliver_pending_telegram_alerts(db) -> dict:
    token_ready = __import__("os").getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_ready = __import__("os").getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token_ready or not chat_ready:
        return {"sent": 0, "failed": 0, "configured": False}

    eligible = db.scalars(
        select(JobRecord).where(
            JobRecord.screening["status"].as_string().in_(["matched", "review"])
        ).order_by(JobRecord.discovered_at.desc()).limit(200)
    ).all()

    sent = failed = 0
    for job in eligible:
        notification = db.scalar(
            select(NotificationRecord).where(
                NotificationRecord.source_job_id == job.source_job_id,
                NotificationRecord.channel == "telegram",
            )
        )
        if notification and notification.delivered:
            continue

        if notification is None:
            notification = NotificationRecord(
                source_job_id=job.source_job_id,
                channel="telegram",
                delivered=False,
                attempts=0,
            )
            db.add(notification)
            db.flush()

        notification.attempts += 1
        ok, error = send_telegram_message(build_job_alert(job))
        notification.delivered = ok
        notification.last_error = error
        notification.updated_at = datetime.now(timezone.utc)
        if ok:
            sent += 1
        else:
            failed += 1
        db.commit()

    return {"sent": sent, "failed": failed, "configured": True}


async def run_discovery_cycle() -> dict:
    # Workers may start before the API process; ensure the current schema exists.
    Base.metadata.create_all(bind=engine)
    # Import lazily to reuse the API's single deduplication and persistence path.
    from app.main import save_job

    with SessionLocal() as db:
        board_records = db.scalars(select(BoardSourceRecord)).all()
        boards = [
            BoardSource(provider=row.provider, slug=row.slug, company_name=row.company_name)
            for row in board_records
        ]
        pref_record = db.get(PreferencesRecord, 1)
        preferences = Preferences.model_validate(
            pref_record.payload if pref_record else {}
        )

        report = await discover_all_with_report(boards)
        jobs = report.jobs
        now = datetime.now(timezone.utc)
        failures_by_key = {
            (failure.provider, failure.slug): failure.error
            for failure in report.failures
        }
        jobs_by_key = {}
        for job in jobs:
            # Source IDs are provider-prefixed; board-specific providers include the slug.
            parts = job.source_job_id.split(":")
            key = (job.source, parts[1] if len(parts) > 2 else "global")
            jobs_by_key[key] = jobs_by_key.get(key, 0) + 1

        for board in boards:
            key = (board.provider, board.slug)
            health = db.scalar(
                select(BoardSourceHealthRecord).where(
                    BoardSourceHealthRecord.provider == board.provider,
                    BoardSourceHealthRecord.slug == board.slug,
                )
            )
            if health is None:
                health = BoardSourceHealthRecord(
                    provider=board.provider,
                    slug=board.slug,
                    last_checked_at=now,
                    last_job_count=0,
                )
                db.add(health)
            health.last_checked_at = now
            health.last_error = failures_by_key.get(key)
            health.last_job_count = jobs_by_key.get(key, 0)
            if key in failures_by_key:
                health.consecutive_failures += 1
            else:
                health.last_success_at = now
                health.consecutive_failures = 0
        db.flush()
        inserted = duplicates = 0
        for job in jobs:
            _, created = save_job(db, job, preferences)
            if created:
                inserted += 1
            else:
                duplicates += 1

        notifications = deliver_pending_telegram_alerts(db)

        return {
    "checked_at": datetime.now(timezone.utc).isoformat(),
    "boards_checked": report.boards_checked,
    "boards_succeeded": report.boards_succeeded,
    "boards_failed": report.boards_failed,
    "discovered": len(jobs),
    "inserted": inserted,
    "duplicates": duplicates,
    "failures": [
        {
            "provider": failure.provider,
            "slug": failure.slug,
            "company": failure.company,
            "error": failure.error,
        }
        for failure in report.failures
    ],
    "telegram": notifications,
}