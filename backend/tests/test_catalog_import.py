import asyncio

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

import app.main as main_module
from app.database import Base
from app.models import BoardSourceRecord
from app.schemas import BoardSource


def test_catalog_import_checks_feed_and_is_idempotent(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    async def fake_discover_board(client, board):
        return [object(), object()]

    monkeypatch.setattr(main_module, "discover_board", fake_discover_board)
    payload = [
        BoardSource(provider="ashby", slug="ramp", company_name="Untrusted display name"),
        BoardSource(provider="ashby", slug="ramp", company_name="Ramp"),
        BoardSource(provider="greenhouse", slug="unknown", company_name="Unknown"),
    ]

    with Session(engine) as db:
        result = asyncio.run(main_module.import_employer_board_catalog(payload, db))

        assert result["imported_count"] == 1
        assert result["skipped_count"] == 1
        assert result["rejected_count"] == 1
        assert result["imported"][0]["company_name"] == "Ramp"
        assert result["imported"][0]["live_jobs_at_import"] == 2
        assert result["skipped"][0]["reason"] == "duplicate_in_request"
        assert result["rejected"][0]["reason"] == "not_in_curated_catalog"

        records = db.scalars(select(BoardSourceRecord)).all()
        assert len(records) == 1
        assert records[0].company_name == "Ramp"
