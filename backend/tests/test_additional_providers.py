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


def test_smartrecruiters_public_posting_extraction():
    payload = {
        "content": [
            {
                "id": "posting-202",
                "name": "Data Engineer",
                "releasedDate": "2026-11-12T08:30:00.000Z",
                "applyUrl": "https://jobs.smartrecruiters.com/Acme/202",
                "location": {
                    "city": "Bengaluru",
                    "region": "Karnataka",
                    "country": "India",
                },
            }
        ]
    }

    def handler(request):
        assert request.url.host == "api.smartrecruiters.com"
        assert request.url.params["destination"] == "PUBLIC"
        return httpx.Response(200, json=payload, request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            board = BoardSource(
                provider="smartrecruiters",
                slug="acme",
                company_name="Acme",
            )
            return await discover_board(client, board)

    jobs = asyncio.run(run())
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "smartrecruiters:acme:posting-202"
    assert jobs[0].title == "Data Engineer"
    assert jobs[0].location == "Bengaluru, Karnataka, India"
    assert jobs[0].country == "India"
    assert jobs[0].posted_at == "2026-11-12T08:30:00+00:00"
    assert str(jobs[0].apply_url) == "https://jobs.smartrecruiters.com/Acme/202"
