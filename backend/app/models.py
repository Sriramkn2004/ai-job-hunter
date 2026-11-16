from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

JsonType = JSON


class PreferencesRecord(Base):
    __tablename__ = "preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    payload: Mapped[dict] = mapped_column(JsonType, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class BoardSourceRecord(Base):
    __tablename__ = "board_sources"
    __table_args__ = (
        UniqueConstraint("provider", "slug", name="uq_board_provider_slug"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class JobRecord(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_job_id: Mapped[str] = mapped_column(
        String(300), unique=True, index=True, nullable=False
    )
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(250), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    country: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    employment_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(12), nullable=True)
    salary_period: Mapped[str | None] = mapped_column(String(30), nullable=True)
    posted_at: Mapped[str | None] = mapped_column(String(80), nullable=True)
    apply_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    screening: Mapped[dict] = mapped_column(JsonType, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class NotificationRecord(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("source_job_id", "channel", name="uq_notification_job_channel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.source_job_id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class BoardSourceHealthRecord(Base):
    __tablename__ = "board_source_health"
    __table_args__ = (
        UniqueConstraint("provider", "slug", name="uq_board_health_provider_slug"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_job_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ApplicationRecord(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("source_job_id", name="uq_application_source_job"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.source_job_id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_email: Mapped[str] = mapped_column(String(254), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft")
    cover_letter: Mapped[str] = mapped_column(Text, nullable=False, default="")
    account_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    account_status: Mapped[str] = mapped_column(String(40), nullable=False, default="not_required")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    submission_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class ApplicationOutcomeRecord(Base):
    __tablename__ = "application_outcomes"
    __table_args__ = (UniqueConstraint("application_id", name="uq_application_outcome_application"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    interview_stage: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    offered_salary: Mapped[str | None] = mapped_column(String(120), nullable=True)
    outcome_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
