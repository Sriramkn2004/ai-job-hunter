from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from pathlib import Path

import httpx

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine, get_db
from app.models import ApplicationRecord, BoardSourceRecord, JobRecord, PreferencesRecord
from app.schemas import ApplicationDraftIn, ApplicationOut, ApplicationUpdateIn, BoardSource, CatalogBoardSelection, JobIn, JobOut, Preferences
from app.screening import evaluate_job, extract_salary
from app.discovery import discover_board


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        changed = False
        if db.get(PreferencesRecord, 1) is None:
            db.add(PreferencesRecord(id=1, payload=Preferences().model_dump()))
            changed = True
        # Remote OK publishes a free public JSON feed; register it by default.
        remoteok = db.scalar(
            select(BoardSourceRecord).where(
                BoardSourceRecord.provider == "remoteok",
                BoardSourceRecord.slug == "global",
            )
        )
        if remoteok is None:
            db.add(BoardSourceRecord(
                provider="remoteok",
                slug="global",
                company_name="Remote OK",
            ))
            changed = True
        if changed:
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


@app.post("/api/v1/sources/boards/bulk")
def add_boards_bulk(payload: list[BoardSource], db: Session = Depends(get_db)):
    """Register up to 100 verified ATS company boards in one request."""
    if not payload:
        raise HTTPException(400, "Provide at least one board source")
    if len(payload) > 100:
        raise HTTPException(400, "A maximum of 100 board sources can be added at once")

    created = []
    existing = []
    seen = set()
    for board in payload:
        key = (board.provider, board.slug.strip().lower())
        if key in seen:
            existing.append({"provider": board.provider, "slug": board.slug, "reason": "duplicate_in_request"})
            continue
        seen.add(key)
        record = db.scalar(
            select(BoardSourceRecord).where(
                BoardSourceRecord.provider == board.provider,
                BoardSourceRecord.slug == board.slug,
            )
        )
        if record is not None:
            existing.append({"provider": board.provider, "slug": board.slug, "reason": "already_registered"})
            continue
        record = BoardSourceRecord(**board.model_dump())
        db.add(record)
        db.flush()
        created.append({
            "id": record.id,
            "provider": record.provider,
            "slug": record.slug,
            "company_name": record.company_name,
        })

    db.commit()
    return {
        "created_count": len(created),
        "skipped_count": len(existing),
        "created": created,
        "skipped": existing,
    }


@app.post("/api/v1/sources/boards/validate")
async def validate_boards(payload: list[BoardSource]):
    """Check public board feeds before registration; this endpoint never saves sources."""
    if not payload:
        raise HTTPException(400, "Provide at least one board source")
    if len(payload) > 25:
        raise HTTPException(400, "A maximum of 25 board sources can be validated at once")

    results = []
    async with httpx.AsyncClient(
        headers={"User-Agent": "AIJobHunter/0.1 (personal job search)"}
    ) as client:
        for board in payload:
            try:
                jobs = await discover_board(client, board)
                results.append({
                    "provider": board.provider,
                    "slug": board.slug,
                    "company_name": board.company_name,
                    "valid": True,
                    "live_jobs": len(jobs),
                    "error": None,
                })
            except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
                results.append({
                    "provider": board.provider,
                    "slug": board.slug,
                    "company_name": board.company_name,
                    "valid": False,
                    "live_jobs": 0,
                    "error": f"{type(exc).__name__}: {exc}",
                })

    valid_count = sum(1 for item in results if item["valid"])
    return {
        "checked_count": len(results),
        "valid_count": valid_count,
        "invalid_count": len(results) - valid_count,
        "total_live_jobs": sum(item["live_jobs"] for item in results),
        "results": results,
        "saved": False,
    }


@app.get("/api/v1/sources/catalog")
def get_employer_board_catalog():
    catalog_path = Path(__file__).resolve().parents[1] / "data" / "employer-board-catalog.json"
    if not catalog_path.is_file():
        raise HTTPException(503, "Employer board catalog is unavailable")
    return json.loads(catalog_path.read_text(encoding="utf-8"))


@app.post("/api/v1/sources/catalog/import")
async def import_employer_board_catalog(
    payload: list[CatalogBoardSelection],
    db: Session = Depends(get_db),
):
    """Live-check selected catalog boards and register only reachable public feeds."""
    if not payload:
        raise HTTPException(400, "Select at least one catalog board")
    if len(payload) > 25:
        raise HTTPException(400, "A maximum of 25 catalog boards can be imported at once")

    catalog_path = Path(__file__).resolve().parents[1] / "data" / "employer-board-catalog.json"
    if not catalog_path.is_file():
        raise HTTPException(503, "Employer board catalog is unavailable")
    catalog_data = json.loads(catalog_path.read_text(encoding="utf-8"))
    allowed = {
        (item["provider"], item["slug"]): item
        for item in catalog_data.get("boards", [])
    }

    imported, skipped, rejected = [], [], []
    seen = set()
    async with httpx.AsyncClient(
        headers={"User-Agent": "AIJobHunter/0.1 (personal job search)"}
    ) as client:
        for board in payload:
            key = (board.provider, board.slug)
            if key in seen:
                skipped.append({
                    "provider": board.provider, "slug": board.slug,
                    "reason": "duplicate_in_request",
                })
                continue
            seen.add(key)
            catalog_item = allowed.get(key)
            if catalog_item is None:
                rejected.append({
                    "provider": board.provider, "slug": board.slug,
                    "reason": "not_in_curated_catalog",
                })
                continue

            existing = db.scalar(
                select(BoardSourceRecord).where(
                    BoardSourceRecord.provider == board.provider,
                    BoardSourceRecord.slug == board.slug,
                )
            )
            if existing is not None:
                skipped.append({
                    "provider": board.provider, "slug": board.slug,
                    "reason": "already_registered",
                })
                continue

            try:
                source = BoardSource(
                    provider=board.provider,
                    slug=board.slug,
                    company_name=catalog_item["company_name"],
                )
                jobs = await discover_board(client, source)
            except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
                rejected.append({
                    "provider": board.provider, "slug": board.slug,
                    "reason": f"{type(exc).__name__}: {exc}",
                })
                continue

            record = BoardSourceRecord(
                provider=board.provider,
                slug=board.slug,
                company_name=catalog_item["company_name"],
            )
            db.add(record)
            db.flush()
            imported.append({
                "id": record.id,
                "provider": board.provider,
                "slug": board.slug,
                "company_name": catalog_item["company_name"],
                "live_jobs_at_import": len(jobs),
                "careers_url": catalog_item["careers_url"],
            })

    db.commit()
    return {
        "imported_count": len(imported),
        "skipped_count": len(skipped),
        "rejected_count": len(rejected),
        "imported": imported,
        "skipped": skipped,
        "rejected": rejected,
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
def list_jobs(
    status: str | None = None,
    country: str | None = None,
    source: str | None = None,
    company: str | None = None,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Search and page through discovered jobs without changing the list response shape."""
    statement = select(JobRecord).order_by(JobRecord.discovered_at.desc(), JobRecord.id.desc())
    if status:
        if status not in {"matched", "review", "skipped"}:
            raise HTTPException(400, "status must be matched, review or skipped")
        statement = statement.where(
            JobRecord.screening["status"].as_string() == status
        )
    if country:
        statement = statement.where(JobRecord.country.ilike(f"%{country.strip()}%"))
    if source:
        statement = statement.where(JobRecord.source.ilike(f"%{source.strip()}%"))
    if company:
        statement = statement.where(JobRecord.company.ilike(f"%{company.strip()}%"))
    if q:
        term = f"%{q.strip()}%"
        statement = statement.where(
            JobRecord.title.ilike(term)
            | JobRecord.company.ilike(term)
            | JobRecord.description.ilike(term)
            | JobRecord.location.ilike(term)
        )
    records = db.scalars(statement.offset(offset).limit(limit)).all()
    return [to_job_out(record) for record in records]

@app.post("/api/v1/jobs/rescreen")
def rescreen_existing_jobs(db: Session = Depends(get_db)):
    preferences_record = db.get(PreferencesRecord, 1)
    preferences = Preferences.model_validate(
        preferences_record.payload if preferences_record else {}
    )

    records = db.scalars(select(JobRecord)).all()

    updated = 0
    salary_extracted = 0
    status_counts = {
        "matched": 0,
        "review": 0,
        "skipped": 0,
    }

    try:
        for record in records:

            # Backfill annual salary period for existing Adzuna records
            if (
                record.source == "adzuna"
                and (record.salary_min is not None or record.salary_max is not None)
                and not record.salary_period
            ):
                record.salary_period = "year"

            # Extract and persist salary when structured salary is unavailable
            if record.salary_min is None and record.salary_max is None:
                extracted = extract_salary(
                    record.description,
                    record.country,
                )

                if extracted:
                    (
                        record.salary_min,
                        record.salary_max,
                        record.salary_currency,
                        record.salary_period,
                    ) = extracted

                    salary_extracted += 1

            job = JobIn(
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
            )

            result = evaluate_job(job, preferences)
            record.screening = result.model_dump()

            status_counts[result.status] += 1
            updated += 1

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "success": True,
        "jobs_rescreened": updated,
        "salary_extracted": salary_extracted,
        "status_counts": status_counts,
        "notifications_sent": 0,
    }

@app.post("/api/v1/discovery/run")
async def run_discovery():
    from app.discovery_service import run_discovery_cycle
    return await run_discovery_cycle()


@app.get("/api/v1/monitoring/boards")
def board_health_status(db: Session = Depends(get_db)):
    from app.models import BoardSourceHealthRecord

    boards = db.scalars(
        select(BoardSourceRecord).order_by(BoardSourceRecord.company_name.asc())
    ).all()
    health_rows = db.scalars(select(BoardSourceHealthRecord)).all()
    health_by_key = {(row.provider, row.slug): row for row in health_rows}
    return [
        {
            "id": board.id,
            "provider": board.provider,
            "slug": board.slug,
            "company_name": board.company_name,
            "last_checked_at": (
                health_by_key[(board.provider, board.slug)].last_checked_at.isoformat()
                if (board.provider, board.slug) in health_by_key else None
            ),
            "last_success_at": (
                health_by_key[(board.provider, board.slug)].last_success_at.isoformat()
                if (board.provider, board.slug) in health_by_key
                and health_by_key[(board.provider, board.slug)].last_success_at else None
            ),
            "last_job_count": (
                health_by_key[(board.provider, board.slug)].last_job_count
                if (board.provider, board.slug) in health_by_key else None
            ),
            "consecutive_failures": (
                health_by_key[(board.provider, board.slug)].consecutive_failures
                if (board.provider, board.slug) in health_by_key else 0
            ),
            "last_error": (
                health_by_key[(board.provider, board.slug)].last_error
                if (board.provider, board.slug) in health_by_key else None
            ),
        }
        for board in boards
    ]


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


def _application_out(application: ApplicationRecord, job: JobRecord) -> ApplicationOut:
    return ApplicationOut(
        id=application.id,
        source_job_id=application.source_job_id,
        candidate_email=application.candidate_email,
        status=application.status,
        cover_letter=application.cover_letter,
        account_required=application.account_required,
        account_status=application.account_status,
        notes=application.notes,
        submission_reference=application.submission_reference,
        approved_at=application.approved_at.isoformat() if application.approved_at else None,
        submitted_at=application.submitted_at.isoformat() if application.submitted_at else None,
        created_at=application.created_at.isoformat(),
        updated_at=application.updated_at.isoformat(),
        company=job.company,
        title=job.title,
        apply_url=job.apply_url,
    )


def _draft_cover_letter(job: JobRecord) -> str:
    # Every claim below is grounded in the candidate's supplied resume.
    role = job.title
    company = job.company
    return (
        f"Dear Hiring Team,\n\n"
        f"I am writing to apply for the {role} position at {company}. "
        "I am a Computer Science and Engineering graduate with hands-on experience "
        "in data protection, process automation, analytics and software development.\n\n"
        "As a Data Protection & Automation Intern at Vontier, I have worked with "
        "Microsoft Purview, Power Automate, Power BI, Snowflake and Azure. I helped "
        "engineer automation workflows that processed more than 10,000 assessments "
        "in approximately 20 minutes, and developed reporting solutions for "
        "assessment tracking, retention schedules and business integrity programmes.\n\n"
        "My technical experience also includes Python, Django, FastAPI, React and SQL. "
        "My projects include a face-recognition-based attendance system, which strengthened my experience "
        "with Python, computer vision and applied software development. I would welcome the opportunity to discuss how "
        "this experience could contribute to your team.\n\n"
        "Thank you for your time and consideration.\n\n"
        "Sincerely,\nSriram K N"
    )


@app.get("/api/v1/applications", response_model=list[ApplicationOut])
def list_applications(db: Session = Depends(get_db)):
    rows = db.execute(
        select(ApplicationRecord, JobRecord)
        .join(JobRecord, ApplicationRecord.source_job_id == JobRecord.source_job_id)
        .order_by(ApplicationRecord.created_at.desc())
    ).all()
    return [_application_out(application, job) for application, job in rows]


@app.post("/api/v1/applications/drafts", response_model=ApplicationOut)
def create_application_draft(payload: ApplicationDraftIn, db: Session = Depends(get_db)):
    job = db.scalar(select(JobRecord).where(JobRecord.source_job_id == payload.source_job_id))
    if job is None:
        raise HTTPException(404, "Job not found")
    if (job.screening or {}).get("status") not in {"matched", "review"}:
        raise HTTPException(400, "Only matched or review jobs can be prepared")
    if "@" not in payload.candidate_email or "." not in payload.candidate_email.rsplit("@", 1)[-1]:
        raise HTTPException(422, "Enter a valid application email address")
    existing = db.scalar(
        select(ApplicationRecord).where(ApplicationRecord.source_job_id == payload.source_job_id)
    )
    if existing:
        if existing.candidate_email != payload.candidate_email:
            existing.candidate_email = payload.candidate_email
            db.commit()
            db.refresh(existing)
        return _application_out(existing, job)
    application = ApplicationRecord(
        source_job_id=job.source_job_id,
        candidate_email=payload.candidate_email,
        cover_letter=_draft_cover_letter(job),
        status="draft",
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return _application_out(application, job)


@app.patch("/api/v1/applications/{application_id}", response_model=ApplicationOut)
def update_application(application_id: int, payload: ApplicationUpdateIn, db: Session = Depends(get_db)):
    application = db.get(ApplicationRecord, application_id)
    if application is None:
        raise HTTPException(404, "Application draft not found")
    if application.status in {"submitted", "withdrawn"}:
        raise HTTPException(409, "Submitted or withdrawn applications are locked")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(application, field, value)
    if application.account_status in {"required", "created", "blocked"}:
        application.account_required = True
    if not application.account_required:
        application.account_status = "not_required"
    db.commit()
    db.refresh(application)
    job = db.scalar(select(JobRecord).where(JobRecord.source_job_id == application.source_job_id))
    return _application_out(application, job)


@app.post("/api/v1/applications/{application_id}/approve", response_model=ApplicationOut)
def approve_application(application_id: int, db: Session = Depends(get_db)):
    application = db.get(ApplicationRecord, application_id)
    if application is None:
        raise HTTPException(404, "Application draft not found")
    if application.status not in {"draft", "ready"}:
        raise HTTPException(409, "Only draft or ready applications can be approved")
    if not application.cover_letter.strip():
        raise HTTPException(400, "Add a cover letter before approval")
    application.status = "approved"
    application.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(application)
    job = db.scalar(select(JobRecord).where(JobRecord.source_job_id == application.source_job_id))
    return _application_out(application, job)


@app.post("/api/v1/applications/{application_id}/record-submission", response_model=ApplicationOut)
def record_application_submission(
    application_id: int,
    confirmation_reference: str = Query(min_length=5, max_length=1000),
    db: Session = Depends(get_db),
):
    application = db.get(ApplicationRecord, application_id)
    if application is None:
        raise HTTPException(404, "Application draft not found")
    if application.status != "approved":
        raise HTTPException(409, "Approve the prepared application before recording submission")
    application.status = "submitted"
    application.submission_reference = confirmation_reference
    application.submitted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(application)
    job = db.scalar(select(JobRecord).where(JobRecord.source_job_id == application.source_job_id))
    return _application_out(application, job)

@app.post("/api/v1/discovery/adzuna")
async def run_adzuna_discovery(
    country: str = "in",
    what: str = "software developer",
    where: str = "Bangalore",
    db: Session = Depends(get_db),
):
    import httpx
    from app.adzuna import (
        discover_adzuna,
        AdzunaConfigurationError,
    )
    from app.discovery_service import deliver_pending_telegram_alerts

    if country not in {"in", "us"}:
        raise HTTPException(400, "Country must be 'in' or 'us'")

    try:
        jobs = await discover_adzuna(
            country=country,
            what=what,
            where=where,
        )
    except AdzunaConfigurationError as exc:
        raise HTTPException(503, str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Adzuna API error: {exc}")
    except ValueError as exc:
        raise HTTPException(502, str(exc))

    pref_record = db.get(PreferencesRecord, 1)
    preferences = Preferences.model_validate(
        pref_record.payload if pref_record else {}
    )

    inserted = duplicates = 0

    for job in jobs:
        _, created = save_job(db, job, preferences)
        if created:
            inserted += 1
        else:
            duplicates += 1

    telegram = deliver_pending_telegram_alerts(db)

    return {
        "provider": "adzuna",
        "country": country,
        "search_term": what,
        "location": where,
        "discovered": len(jobs),
        "inserted": inserted,
        "duplicates": duplicates,
        "telegram": telegram,
    }

