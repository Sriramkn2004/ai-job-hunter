from app.schemas import Preferences, JobIn
from app.screening import evaluate_job


def make_job(
    country="USA",
    currency="USD",
    salary_min=40000,
    salary_max=None,
    period="year",
    job_id="test-1",
):
    return JobIn(
        source="test",
        source_job_id=job_id,
        company="Acme",
        title="Python Developer",
        description="Build Python backend APIs",
        location="Remote",
        country=country,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=currency,
        salary_period=period,
    )


def test_matching_india_job_meets_threshold():
    prefs = Preferences()
    job = make_job(
        country="India",
        currency="INR",
        salary_min=1_800_000,
        job_id="india-1",
    )
    result = evaluate_job(job, prefs)
    assert result.status == "matched"
    assert result.score >= 90


def test_unknown_salary_goes_to_review():
    prefs = Preferences()
    job = make_job(
        country="India",
        currency=None,
        salary_min=None,
        job_id="india-2",
    )
    result = evaluate_job(job, prefs)
    assert result.status == "review"
    assert result.missing_information


def test_usa_salary_below_threshold_is_skipped():
    result = evaluate_job(
        make_job(salary_min=35000, job_id="usa-1"),
        Preferences(),
    )
    assert result.status == "skipped"


def test_usa_salary_at_threshold_is_matched():
    result = evaluate_job(
        make_job(salary_min=40000, job_id="usa-2"),
        Preferences(),
    )
    assert result.status == "matched"


def test_usa_salary_above_threshold_is_matched():
    result = evaluate_job(
        make_job(salary_min=50000, job_id="usa-3"),
        Preferences(),
    )
    assert result.status == "matched"


def test_usa_salary_range_crossing_threshold_goes_to_review():
    result = evaluate_job(
        make_job(
            salary_min=30000,
            salary_max=45000,
            job_id="usa-4",
        ),
        Preferences(),
    )
    assert result.status == "review"
    assert result.missing_information


def test_usa_missing_salary_goes_to_review():
    result = evaluate_job(
        make_job(
            salary_min=None,
            salary_max=None,
            job_id="usa-5",
        ),
        Preferences(),
    )
    assert result.status == "review"


def test_usd_salary_cannot_pass_india_screening():
    result = evaluate_job(
        make_job(
            country="India",
            currency="USD",
            salary_min=50000,
            job_id="india-3",
        ),
        Preferences(),
    )
    assert result.status == "review"


def test_india_salary_below_threshold_is_skipped():
    result = evaluate_job(
        make_job(
            country="India",
            currency="INR",
            salary_min=1_000_000,
            job_id="india-4",
        ),
        Preferences(),
    )
    assert result.status == "skipped"



def test_india_maximum_salary_below_threshold_is_skipped():
    result = evaluate_job(
        make_job(
            country="India",
            currency="INR",
            salary_min=None,
            salary_max=1_000_000,
            period="year",
            job_id="india-max-low",
        ),
        Preferences(),
    )
    assert result.status == "skipped"


def test_india_maximum_salary_at_or_above_threshold_requires_review():
    result = evaluate_job(
        make_job(
            country="India",
            currency="INR",
            salary_min=None,
            salary_max=2_000_000,
            period="year",
            job_id="india-max-high",
        ),
        Preferences(),
    )
    assert result.status == "review"
    assert "Minimum salary is not disclosed" in result.missing_information


def test_usa_maximum_salary_below_threshold_is_skipped():
    result = evaluate_job(
        make_job(
            country="USA",
            currency="USD",
            salary_min=None,
            salary_max=30_000,
            period="year",
            job_id="usa-max-low",
        ),
        Preferences(),
    )
    assert result.status == "skipped"


def test_usa_maximum_salary_at_or_above_threshold_requires_review():
    result = evaluate_job(
        make_job(
            country="USA",
            currency="USD",
            salary_min=None,
            salary_max=60_000,
            period="year",
            job_id="usa-max-high",
        ),
        Preferences(),
    )
    assert result.status == "review"
    assert "Minimum salary is not disclosed" in result.missing_information
