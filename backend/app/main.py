from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
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


app = FastAPI(title="AI Job Hunter API", version="0.2.0", lifespan=lifespan)


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
    return {"status": "ok", "service": "ai-job-hunter", "version": "0.2.0"}


@app.get("/api/v1/preferences")
def get_preferences(db: Session = Depends(get_db)):
    record = db.get(PreferencesRecord, 1)
    if record is None:
        return Preferences().model_dump()
    return record.payload


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
    if record is None:
        record = BoardSourceRecord(**payload.model_dump())
        db.add(record)
        db.commit()
    return {"saved": True, "provider": payload.provider, "slug": payload.slug}


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
async def run_discovery(db: Session = Depends(get_db)):
    from app.discovery import discover_all

    board_records = db.scalars(select(BoardSourceRecord)).all()
    boards = [
        BoardSource(provider=row.provider, slug=row.slug, company_name=row.company_name)
        for row in board_records
    ]
    preferences_record = db.get(PreferencesRecord, 1)
    preferences = Preferences.model_validate(
        preferences_record.payload if preferences_record else {}
    )

    discovered = await discover_all(boards)
    inserted = duplicates = 0
    for job in discovered:
        _, created = save_job(db, job, preferences)
        if created:
            inserted += 1
        else:
            duplicates += 1
    return {"discovered": len(discovered), "inserted": inserted, "duplicates": duplicates}


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
    # This records approval for preparation only; no external form is submitted.
    return {
        "status": "approved_for_preparation",
        "job": record.title,
        "message": "Approval recorded. A permitted source-specific submission adapter is not enabled yet.",
    }
