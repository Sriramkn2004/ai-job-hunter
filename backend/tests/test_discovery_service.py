import asyncio
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.discovery_service as service
from app.database import Base
from app.discovery import DiscoveryReport
from app.models import BoardSourceHealthRecord, BoardSourceRecord


def test_empty_successful_scan_persists_board_health(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(service, "engine", engine)
    monkeypatch.setattr(service, "SessionLocal", sessions)

    with Session(engine) as db:
        db.add(BoardSourceRecord(
            provider="greenhouse",
            slug="empty-board",
            company_name="Empty Board",
        ))
        db.commit()

    async def fake_discover_all_with_report(boards):
        return DiscoveryReport(
            boards_checked=1,
            boards_succeeded=1,
            boards_failed=0,
            jobs=[],
            board_job_counts={("greenhouse", "empty-board"): 0},
        )

    monkeypatch.setattr(service, "discover_all_with_report", fake_discover_all_with_report)

    result = asyncio.run(service.run_discovery_cycle())

    assert result["boards_checked"] == 1
    assert result["discovered"] == 0
    with Session(engine) as db:
        health = db.scalar(select(BoardSourceHealthRecord))
        assert health is not None
        assert health.provider == "greenhouse"
        assert health.slug == "empty-board"
        assert health.last_job_count == 0
        assert health.last_success_at is not None
        assert health.consecutive_failures == 0
