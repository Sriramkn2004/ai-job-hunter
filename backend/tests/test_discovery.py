
import asyncio

import httpx

from app.schemas import BoardSource
from app.discovery import discover_board, discover_all


def test_greenhouse_job_extraction():
    payload = {
        "jobs": [
            {
                "id": 12345,
                "title": "Python Developer",
                "content": "Build backend applications",
                "location": {"name": "Bangalore, India"},
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/12345",
            }
        ]
    }

    def handler(request):
        return httpx.Response(200, json=payload, request=request)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            board = BoardSource(
                provider="greenhouse",
                slug="acme",
                company_name="Acme",
            )
            jobs = await discover_board(client, board)

        assert len(jobs) == 1
        assert jobs[0].source == "greenhouse"
        assert jobs[0].source_job_id == "greenhouse:12345"
        assert jobs[0].company == "Acme"
        assert jobs[0].title == "Python Developer"
        assert jobs[0].location == "Bangalore, India"
        assert jobs[0].country == "India"

    asyncio.run(run())


def test_lever_job_extraction():
    payload = [
        {
            "id": "lever-123",
            "text": "Backend Developer",
            "descriptionPlain": "Develop backend services",
            "categories": {
                "location": "Bangalore",
                "commitment": "Full-time",
            },
            "hostedUrl": "https://jobs.lever.co/acme/lever-123",
        }
    ]

    def handler(request):
        return httpx.Response(200, json=payload, request=request)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            board = BoardSource(
                provider="lever",
                slug="acme",
                company_name="Acme",
            )
            jobs = await discover_board(client, board)

        assert len(jobs) == 1
        assert jobs[0].source == "lever"
        assert jobs[0].source_job_id == "lever:lever-123"
        assert jobs[0].company == "Acme"
        assert jobs[0].title == "Backend Developer"
        assert jobs[0].location == "Bangalore"
        assert jobs[0].country == "India"
        assert jobs[0].employment_type == "Full-time"

    asyncio.run(run())


def test_discovery_handles_http_errors():
    def handler(request):
        return httpx.Response(503, request=request)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            board = BoardSource(
                provider="greenhouse",
                slug="unavailable-company",
                company_name="Unavailable Company",
            )

            try:
                await discover_board(client, board)
                assert False, "Expected HTTPStatusError"
            except httpx.HTTPStatusError:
                pass

    asyncio.run(run())


def test_discover_all_continues_after_one_board_fails(monkeypatch):
    import app.discovery as discovery_module
    from app.schemas import JobIn

    async def fake_discover_board(client, board):
        if board.slug == "unavailable":
            raise httpx.ConnectError(
                "Connection failed",
                request=httpx.Request("GET", "https://example.com"),
            )

        return [
            JobIn(
                source="greenhouse",
                source_job_id="greenhouse:456",
                company=board.company_name,
                title="Python Developer",
                description="Build APIs",
                location="Bangalore",
                apply_url="https://example.com/jobs/456",
            )
        ]

    monkeypatch.setattr(
        discovery_module,
        "discover_board",
        fake_discover_board,
    )

    async def run():
        boards = [
            BoardSource(
                provider="greenhouse",
                slug="unavailable",
                company_name="Unavailable Company",
            ),
            BoardSource(
                provider="greenhouse",
                slug="working",
                company_name="Working Company",
            ),
        ]

        return await discovery_module.discover_all(boards)

    jobs = asyncio.run(run())

    assert len(jobs) == 1
    assert jobs[0].company == "Working Company"
    assert jobs[0].source_job_id == "greenhouse:456"


def test_greenhouse_empty_listing():
    def handler(request):
        return httpx.Response(200, json={"jobs": []}, request=request)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            board = BoardSource(
                provider="greenhouse",
                slug="empty-company",
                company_name="Empty Company",
            )
            jobs = await discover_board(client, board)

        assert jobs == []

    asyncio.run(run())


def test_discovery_report_tracks_success_and_failure(monkeypatch):
    import app.discovery as discovery_module
    from app.schemas import JobIn

    async def fake_discover_board(client, board):
        if board.slug == "unavailable":
            raise httpx.ConnectError(
                "Connection failed",
                request=httpx.Request("GET", "https://example.com"),
            )

        return [
            JobIn(
                source="greenhouse",
                source_job_id="greenhouse:789",
                company=board.company_name,
                title="Python Developer",
                description="Build APIs",
                location="Bangalore",
                apply_url="https://example.com/jobs/789",
            )
        ]

    monkeypatch.setattr(
        discovery_module,
        "discover_board",
        fake_discover_board,
    )

    async def run():
        boards = [
            BoardSource(
                provider="greenhouse",
                slug="working",
                company_name="Working Company",
            ),
            BoardSource(
                provider="greenhouse",
                slug="unavailable",
                company_name="Unavailable Company",
            ),
        ]
        return await discovery_module.discover_all_with_report(boards)

    report = asyncio.run(run())

    assert report.boards_checked == 2
    assert report.boards_succeeded == 1
    assert report.boards_failed == 1
    assert len(report.jobs) == 1
    assert len(report.failures) == 1
    assert report.failures[0].company == "Unavailable Company"
    assert "ConnectError" in report.failures[0].error


def test_discovery_report_handles_empty_successful_board(monkeypatch):
    import app.discovery as discovery_module

    async def fake_discover_board(client, board):
        return []

    monkeypatch.setattr(
        discovery_module,
        "discover_board",
        fake_discover_board,
    )

    async def run():
        board = BoardSource(
            provider="greenhouse",
            slug="empty",
            company_name="Empty Company",
        )
        return await discovery_module.discover_all_with_report([board])

    report = asyncio.run(run())

    assert report.boards_checked == 1
    assert report.boards_succeeded == 1
    assert report.boards_failed == 0
    assert report.jobs == []
    assert report.failures == []


def test_ashby_job_extraction():
    payload = {
        "jobs": [
            {
                "title": "AI Engineer",
                "location": "Bangalore, India",
                "descriptionPlain": "Build AI applications",
                "publishedAt": "2026-11-14T08:00:00Z",
                "employmentType": "FullTime",
                "jobUrl": "https://jobs.ashbyhq.com/acme/job-123",
                "applyUrl": "https://jobs.ashbyhq.com/acme/job-123/application",
                "address": {
                    "postalAddress": {
                        "addressCountry": "India"
                    }
                },
            }
        ]
    }

    def handler(request):
        return httpx.Response(200, json=payload, request=request)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            board = BoardSource(
                provider="ashby",
                slug="acme",
                company_name="Acme",
            )
            jobs = await discover_board(client, board)

        assert len(jobs) == 1
        assert jobs[0].source == "ashby"
        assert jobs[0].title == "AI Engineer"
        assert jobs[0].location == "Bangalore, India"
        assert jobs[0].country == "India"
        assert jobs[0].employment_type == "FullTime"
        assert jobs[0].posted_at == "2026-11-14T08:00:00Z"

        # Pydantic converts this field to HttpUrl.
        assert str(jobs[0].apply_url) == (
            "https://jobs.ashbyhq.com/acme/job-123/application"
        )

    asyncio.run(run())
