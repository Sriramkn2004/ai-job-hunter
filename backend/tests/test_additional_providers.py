import asyncio

import httpx

from app.discovery import discover_board
from app.schemas import BoardSource


def test_remoteok_feed_extraction(monkeypatch):
    payload = [
        {"legal": "metadata"},
        {
            "id": "remote-101",
            "position": "Python Backend Engineer",
            "company": "Remote Acme",
            "description": "Build APIs",
            "location": "Worldwide",
            "date": "2026-11-13T10:00:00Z",
            "url": "https://remoteok.com/remote-jobs/remote-101",
            "apply_url": "https://remoteok.com/remote-jobs/remote-101",
        },
    ]

    def handler(request):
        assert request.url.host == "remoteok.com"
        return httpx.Response(200, json=payload, request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            board = BoardSource(provider="remoteok", slug="global", company_name="Remote OK")
            return await discover_board(client, board)

    jobs = asyncio.run(run())
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "remoteok:remote-101"
    assert jobs[0].company == "Remote Acme"
    assert jobs[0].title == "Python Backend Engineer"
    assert jobs[0].posted_at == "2026-11-13T10:00:00+00:00"
    assert str(jobs[0].apply_url) == "https://remoteok.com/remote-jobs/remote-101"


def test_smartrecruiters_fetches_full_public_posting():
    listing = {
        "totalFound": 1,
        "content": [
            {
                "id": "posting-202",
                "name": "Data Engineer",
                "releasedDate": "2026-11-12T08:30:00.000Z",
                "location": {"city": "Bengaluru", "region": "Karnataka", "country": "IN"},
            }
        ],
    }
    detail = {
        "id": "posting-202",
        "name": "Data Engineer",
        "releasedDate": "2026-11-12T08:30:00.000Z",
        "applyUrl": "https://www.smartrecruiters.com/Acme/202",
        "company": {"name": "Acme Ltd"},
        "location": {"city": "Bengaluru", "region": "Karnataka", "country": "IN"},
        "typeOfEmployment": {"label": "Full-time"},
        "jobAd": {"sections": {
            "jobDescription": {"text": "Build data pipelines"},
            "qualifications": {"text": "Python and SQL"},
        }},
    }

    def handler(request):
        assert request.url.host == "api.smartrecruiters.com"
        if request.url.path.endswith("/postings"):
            assert request.url.params["destination"] == "PUBLIC"
            return httpx.Response(200, json=listing, request=request)
        assert request.url.path.endswith("/postings/posting-202")
        return httpx.Response(200, json=detail, request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            board = BoardSource(provider="smartrecruiters", slug="acme", company_name="Acme")
            return await discover_board(client, board)

    jobs = asyncio.run(run())
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "smartrecruiters:acme:posting-202"
    assert jobs[0].company == "Acme Ltd"
    assert jobs[0].title == "Data Engineer"
    assert jobs[0].location == "Bengaluru, Karnataka, IN"
    assert jobs[0].country == "India"
    assert jobs[0].employment_type == "Full-time"
    assert jobs[0].description == "Build data pipelines\\n\\nPython and SQL"
    assert jobs[0].posted_at == "2026-11-12T08:30:00+00:00"
    assert str(jobs[0].apply_url) == "https://www.smartrecruiters.com/Acme/202"
