from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine, get_db
from app.models import BoardSourceRecord, JobRecord, PreferencesRecord
from app.schemas import BoardSource, JobIn, JobOut, Preferences
from app.screening import evaluate_job


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.get(PreferencesRecord, 1) is None:
            db.add(PreferencesRecord(id=1, payload=Preferences().model_dump()))
            db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="AI Job Hunter API", version="0.3.0", lifespan=lifespan)


def to_job_out(record: JobRecord) -> JobOut:
    return JobOut(
        source=record.source,
        source_job_id=record.source_job_id,
        company=record.company,
        title=record.title,
        description=record.description,
        location=record.location,
        country=record.country,
        employment_type=record.employment_type,
        salary_min=record.salary_min,
        salary_max=record.salary_max,
        salary_currency=record.salary_currency,
        salary_period=record.salary_period,
        posted_at=record.posted_at,
        apply_url=record.apply_url,
        screening=record.screening,
    )


def save_job(db: Session, payload: JobIn, preferences: Preferences) -> tuple[JobOut, bool]:
    existing = db.scalar(
        select(JobRecord).where(JobRecord.source_job_id == payload.source_job_id)
    )
    if existing:
        return to_job_out(existing), False

    data = payload.model_dump()
    data["apply_url"] = str(payload.apply_url) if payload.apply_url else None
    screening = evaluate_job(payload, preferences)
    record = JobRecord(**data, screening=screening.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return to_job_out(record), True


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-job-hunter", "version": "0.3.0"}


@app.get("/api/v1/preferences")
def get_preferences(db: Session = Depends(get_db)):
    record = db.get(PreferencesRecord, 1)
    return record.payload if record else Preferences().model_dump()


@app.put("/api/v1/preferences")
def update_preferences(payload: Preferences, db: Session = Depends(get_db)):
    record = db.get(PreferencesRecord, 1)
    if record is None:
        record = PreferencesRecord(id=1, payload=payload.model_dump())
        db.add(record)
    else:
        record.payload = payload.model_dump()
    db.commit()
    return payload.model_dump()


@app.post("/api/v1/sources/boards")
def add_board(payload: BoardSource, db: Session = Depends(get_db)):
    record = db.scalar(
        select(BoardSourceRecord).where(
            BoardSourceRecord.provider == payload.provider,
            BoardSourceRecord.slug == payload.slug,
        )
    )
    created = record is None
    if created:
        record = BoardSourceRecord(**payload.model_dump())
        db.add(record)
        db.commit()
        db.refresh(record)
    return {
        "saved": True,
        "created": created,
        "id": record.id,
        "provider": record.provider,
        "slug": record.slug,
        "company_name": record.company_name,
    }


@app.get("/api/v1/sources/boards")
def list_boards(db: Session = Depends(get_db)):
    records = db.scalars(
        select(BoardSourceRecord).order_by(
            BoardSourceRecord.company_name.asc(),
            BoardSourceRecord.provider.asc(),
        )
    ).all()
    return [
        {
            "id": row.id,
            "provider": row.provider,
            "slug": row.slug,
            "company_name": row.company_name,
            "created_at": row.created_at.isoformat(),
        }
        for row in records
    ]


@app.delete("/api/v1/sources/boards/{board_id}")
def remove_board(board_id: int, db: Session = Depends(get_db)):
    record = db.get(BoardSourceRecord, board_id)
    if record is None:
        raise HTTPException(404, "Board source not found")
    db.delete(record)
    db.commit()
    return {"deleted": True, "id": board_id}


@app.post("/api/v1/jobs", response_model=JobOut)
def ingest_job(payload: JobIn, db: Session = Depends(get_db)):
    preferences_record = db.get(PreferencesRecord, 1)
    preferences = Preferences.model_validate(
        preferences_record.payload if preferences_record else {}
    )
    job, _ = save_job(db, payload, preferences)
    return job


@app.get("/api/v1/jobs", response_model=list[JobOut])
def list_jobs(status: str | None = None, db: Session = Depends(get_db)):
    records = db.scalars(select(JobRecord).order_by(JobRecord.discovered_at.desc())).all()
    jobs = [to_job_out(record) for record in records]
    if status:
        jobs = [job for job in jobs if job.screening and job.screening.status == status]
    return jobs


@app.post("/api/v1/discovery/run")
async def run_discovery():
    from app.discovery_service import run_discovery_cycle
    return await run_discovery_cycle()


@app.get("/api/v1/monitoring/status")
def monitoring_status(db: Session = Depends(get_db)):
    from app.models import NotificationRecord
    from sqlalchemy import func
    from app.celery_app import DISCOVERY_INTERVAL_SECONDS

    total_jobs = db.scalar(select(func.count()).select_from(JobRecord)) or 0
    matched_jobs = db.scalar(
        select(func.count()).select_from(JobRecord).where(
            JobRecord.screening["status"].as_string().in_(["matched", "review"])
        )
    ) or 0
    sent_notifications = db.scalar(
        select(func.count()).select_from(NotificationRecord).where(
            NotificationRecord.delivered.is_(True),
            NotificationRecord.channel == "telegram",
        )
    ) or 0
    return {
        "scheduler_interval_seconds": DISCOVERY_INTERVAL_SECONDS,
        "registered_boards": db.scalar(select(func.count()).select_from(BoardSourceRecord)) or 0,
        "jobs_stored": total_jobs,
        "jobs_needing_attention": matched_jobs,
        "telegram_notifications_sent": sent_notifications,
        "telegram_configured": bool(
            __import__("os").getenv("TELEGRAM_BOT_TOKEN")
            and __import__("os").getenv("TELEGRAM_CHAT_ID")
        ),
    }


@app.post("/api/v1/notifications/telegram/test")
def test_telegram():
    from app.notifications import send_telegram_message
    ok, error = send_telegram_message("✅ <b>AI Job Hunter</b> Telegram notifications are connected.")
    if not ok:
        raise HTTPException(400, error or "Telegram message failed")
    return {"sent": True}


@app.post("/api/v1/applications/{source_job_id}/approve")
def approve_application(source_job_id: str, db: Session = Depends(get_db)):
    record = db.scalar(
        select(JobRecord).where(JobRecord.source_job_id == source_job_id)
    )
    if record is None:
        raise HTTPException(404, "Job not found")
    status = (record.screening or {}).get("status")
    if status not in {"matched", "review"}:
        raise HTTPException(400, "This job is not eligible for review")
    return {
        "status": "approved_for_preparation",
        "job": record.title,
        "message": "Approval recorded. A permitted source-specific submission adapter is not enabled yet.",
    }
