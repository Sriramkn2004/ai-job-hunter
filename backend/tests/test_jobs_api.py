from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import list_jobs
from app.models import JobRecord


def _job(source_job_id, company, title, country, status, location):
    return JobRecord(
        source_job_id=source_job_id,
        source="greenhouse",
        company=company,
        title=title,
        description=f"{title} role",
        location=location,
        country=country,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        salary_period=None,
        posted_at=None,
        apply_url=None,
        screening={"status": status, "score": 80, "reasons": [], "missing_information": []},
    )


def test_jobs_api_filters_search_and_paginates():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        db.add_all([
            _job("1", "Acme", "Python Developer", "India", "matched", "Bengaluru"),
            _job("2", "Globex", "Data Engineer", "USA", "review", "Remote"),
            _job("3", "Acme", "Backend Developer", "India", "matched", "Pune"),
        ])
        db.commit()

        india_jobs = list_jobs(
            status="matched", country="India", source=None, company=None,
            q="Developer", limit=1, offset=0, db=db,
        )
        assert len(india_jobs) == 1
        assert india_jobs[0].company == "Acme"
        assert india_jobs[0].screening.status == "matched"

        second_page = list_jobs(
            status="matched", country="India", source=None, company=None,
            q="Developer", limit=1, offset=1, db=db,
        )
        assert len(second_page) == 1
        assert second_page[0].source_job_id == "1"

        company_search = list_jobs(
            status=None, country=None, source=None, company="Globex",
            q=None, limit=50, offset=0, db=db,
        )
        assert len(company_search) == 1
        assert company_search[0].title == "Data Engineer"
