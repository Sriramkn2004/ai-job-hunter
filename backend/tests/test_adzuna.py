import asyncio

import httpx

from app.adzuna import discover_adzuna


def test_adzuna_normalizes_india_job(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "test-app-id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "test-app-key")
    payload = {
        "results": [
            {
                "id": "123",
                "title": "Python Backend Developer",
                "description": "Build APIs",
                "redirect_url": "https://adzuna.example/jobs/123",
                "location": {"display_name": "Bengaluru, Karnataka"},
                "company": {"display_name": "Example Ltd"},
                "salary_min": 1800000,
                "salary_max": 2200000,
                "created": "2026-11-15T10:00:00Z",
            }
        ]
    }

    def handler(request):
        assert request.url.host == "api.adzuna.com"
        assert request.url.params["app_id"] == "test-app-id"
        return httpx.Response(200, json=payload, request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            # Patch the client constructor used by the provider while retaining
            # MockTransport so the test never makes a network request.
            import app.adzuna as adzuna_module
            original_client = adzuna_module.httpx.AsyncClient
            adzuna_module.httpx.AsyncClient = lambda **kwargs: original_client(
                transport=httpx.MockTransport(handler),
                headers=kwargs.get("headers"),
            )
            try:
                return await discover_adzuna("in", "Python Developer", "Bangalore")
            finally:
                adzuna_module.httpx.AsyncClient = original_client

    jobs = asyncio.run(run())
    assert len(jobs) == 1
    assert jobs[0].source == "adzuna"
    assert jobs[0].source_job_id == "adzuna:in:123"
    assert jobs[0].country == "India"
    assert jobs[0].salary_currency == "INR"
    assert jobs[0].salary_period == "year"
    assert str(jobs[0].apply_url) == "https://adzuna.example/jobs/123"


def test_adzuna_requires_credentials(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)

    async def run():
        try:
            await discover_adzuna("in", "Python Developer", "Bangalore")
        except Exception as exc:
            assert "credentials are not configured" in str(exc)
        else:
            raise AssertionError("Missing Adzuna credentials must be rejected")
