from types import SimpleNamespace

from app.notifications import build_job_alert


def test_job_alert_includes_role_company_and_discovery_disclaimer():
    job = SimpleNamespace(
        title="Python Developer",
        company="Example Corp",
        location="Bengaluru",
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        salary_period=None,
        apply_url="https://example.com/jobs/123",
        screening={"score": 90},
    )
    message = build_job_alert(job)
    assert "Python Developer" in message
    assert "Example Corp" in message
    assert "90/100" in message
    assert "not an application confirmation" in message
