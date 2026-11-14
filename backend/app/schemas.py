from pydantic import BaseModel, Field, HttpUrl
from typing import Literal

DEFAULT_ROLES = [
    "Software Engineer", "Python Developer", "Backend Developer",
    "AI/ML Engineer", "Data Engineer", "Data Analyst",
    "Data Privacy Engineer", "Privacy Analyst", "Privacy Engineer",
    "Data Governance Analyst", "Automation Engineer", "RPA Developer",
    "Full Stack Developer", "DevOps Engineer", "Cybersecurity Engineer",
    "Information Security Analyst", "Security Engineer",
    "Business Intelligence Analyst", "Analytics Engineer",
    "Machine Learning Engineer",
]

class Preferences(BaseModel):
    markets: list[str] = ["India", "USA", "Other international markets"]
    roles: list[str] = DEFAULT_ROLES
    india_min_ctc_lpa: float = 15
    usa_min_salary_usd_annual: float = 40000
    preferred_locations: list[str] = ["Bangalore"]
    include_remote: bool = True
    experience_levels: list[str] = ["Fresher", "0-2 years"]
    minimum_match_score: int = Field(default=75, ge=0, le=100)
    application_mode: Literal["hybrid"] = "hybrid"
    auto_apply_min_score: int = Field(default=90, ge=0, le=100)
    salary_unknown_policy: Literal["review", "skip"] = "review"

class BoardSource(BaseModel):
    provider: Literal["greenhouse", "lever", "ashby", "recruitee", "smartrecruiters", "remoteok", "workable", "personio"]
    slug: str = Field(min_length=1, max_length=120)
    company_name: str = Field(min_length=1, max_length=200)

class JobIn(BaseModel):
    source: str
    source_job_id: str
    company: str
    title: str
    description: str = ""
    location: str = ""
    country: str = ""
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    posted_at: str | None = None
    apply_url: HttpUrl | None = None

class Screening(BaseModel):
    status: Literal["matched", "review", "skipped"]
    score: int
    reasons: list[str] = []
    missing_information: list[str] = []

class JobOut(JobIn):
    screening: Screening | None = None


class CatalogBoardSelection(BaseModel):
    """A selection from the curated catalog; company names are server-controlled."""
    provider: Literal["greenhouse", "lever", "ashby", "recruitee", "smartrecruiters", "remoteok", "workable", "personio"]
    slug: str = Field(min_length=1, max_length=120)
