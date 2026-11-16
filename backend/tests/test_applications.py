from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import (
    approve_application,
    create_application_draft,
    list_applications,
    record_application_submission,
    update_application,
)
from app.models import JobRecord
from app.schemas import ApplicationDraftIn, ApplicationUpdateIn


def _database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def _job(db):
    record = JobRecord(
        source_job_id="gh:role-123",
        source="greenhouse",
        company="Example Employer",
        title="Python Developer",
        description="Build Python services and automate workflows.",
        location="Bengaluru",
        country="India",
        employment_type="Full-time",
        salary_min=1_800_000,
        salary_max=2_000_000,
        salary_currency="INR",
        salary_period="year",
        posted_at=None,
        apply_url="https://example.com/jobs/123",
        screening={"status": "matched", "score": 90, "reasons": [], "missing_information": []},
    )
    db.add(record)
    db.commit()
    return record


def test_application_draft_approval_and_submission_tracking():
    with _database() as db:
        _job(db)
        draft = create_application_draft(
            ApplicationDraftIn(
                source_job_id="gh:role-123",
                candidate_email="sriramkn2004@gmail.com",
            ),
            db,
        )
        assert draft.status == "draft"
        assert "Vontier" in draft.cover_letter
        assert "10,000" in draft.cover_letter
        assert "20 minutes" in draft.cover_letter
        assert "face-recognition-based attendance system" in draft.cover_letter
        assert "NET-PATROL-X" not in draft.cover_letter
        assert "15 minutes" not in draft.cover_letter

        saved = update_application(
            draft.id,
            ApplicationUpdateIn(
                account_required=True,
                account_status="required",
                notes="Employer account needs to be created.",
            ),
            db,
        )
        assert saved.account_required is True
        assert saved.account_status == "required"

        approved = approve_application(draft.id, db)
        assert approved.status == "approved"
        assert approved.submitted_at is None

        submitted = record_application_submission(
            draft.id,
            confirmation_reference="https://example.com/application-confirmation/123",
            db=db,
        )
        assert submitted.status == "submitted"
        assert submitted.submission_reference.endswith("/123")
        assert submitted.submitted_at is not None

        rows = list_applications(db)
        assert len(rows) == 1
        assert rows[0].candidate_email == "sriramkn2004@gmail.com"


def test_application_draft_rejects_skipped_job():
    with _database() as db:
        record = _job(db)
        record.screening = {"status": "skipped", "score": 20, "reasons": [], "missing_information": []}
        db.commit()
        try:
            create_application_draft(
                ApplicationDraftIn(
                    source_job_id=record.source_job_id,
                    candidate_email="sriramkn2004@gmail.com",
                ),
                db,
            )
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 400
        else:
            raise AssertionError("Skipped jobs must not create application drafts")
