from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import add_boards_bulk
from app.models import BoardSourceRecord
from app.schemas import BoardSource


def test_bulk_board_registration_deduplicates_and_is_idempotent():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        payload = [
            BoardSource(provider="greenhouse", slug="acme", company_name="Acme"),
            BoardSource(provider="lever", slug="globex", company_name="Globex"),
            BoardSource(provider="greenhouse", slug="acme", company_name="Acme"),
        ]
        result = add_boards_bulk(payload, db)

        assert result["created_count"] == 2
        assert result["skipped_count"] == 1
        assert result["skipped"][0]["reason"] == "duplicate_in_request"
        assert len(db.scalars(select(BoardSourceRecord)).all()) == 2

        second = add_boards_bulk(payload[:2], db)
        assert second["created_count"] == 0
        assert second["skipped_count"] == 2
        assert all(item["reason"] == "already_registered" for item in second["skipped"])
