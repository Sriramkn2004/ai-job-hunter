from app.schemas import Preferences, JobIn
from app.screening import evaluate_job

def test_matching_india_job_meets_threshold():
    prefs = Preferences()
    job = JobIn(
        source="test", source_job_id="1", company="Acme",
        title="Python Developer", description="Build Python backend APIs",
        location="Bangalore", country="India",
        salary_min=1_800_000, salary_currency="INR", salary_period="year",
    )
    result = evaluate_job(job, prefs)
    assert result.status == "matched"
    assert result.score >= 90

def test_unknown_salary_goes_to_review():
    prefs = Preferences()
    job = JobIn(
        source="test", source_job_id="2", company="Acme",
        title="Python Developer", description="Build Python backend APIs",
        location="Bangalore", country="India",
    )
    result = evaluate_job(job, prefs)
    assert result.status == "review"
    assert result.missing_information
