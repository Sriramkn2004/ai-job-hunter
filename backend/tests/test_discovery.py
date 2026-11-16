
import asyncio

import httpx

from app.schemas import BoardSource
from app.discovery import discover_board, discover_all, infer_country, normalize_posted_at


def test_greenhouse_job_extraction():
    payload = {
        "jobs": [
            {
                "id": 12345,
                "title": "Python Developer",
                "content": "Build backend applications",
                "location": {"name": "Bangalore, India"},
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/12345",
                "first_published": "2026-11-12T09:30:00Z",
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
            "createdAt": 1794475800000,
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
        assert jobs[0].posted_at == "2026-11-12T09:30:00+00:00"

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
        assert jobs[0].posted_at == "2026-11-14T08:00:00+00:00"

        # Pydantic converts this field to HttpUrl.
        assert str(jobs[0].apply_url) == (
            "https://jobs.ashbyhq.com/acme/job-123/application"
        )

    asyncio.run(run())



def test_country_inference_does_not_match_indiana_as_india():
    assert infer_country("Indianapolis, Indiana, USA") == "USA"
    assert infer_country("Indiana") == ""


def test_country_inference_recognizes_bengaluru():
    assert infer_country("Bengaluru, Karnataka") == "India"


def test_posted_at_normalizes_epoch_milliseconds():
    assert normalize_posted_at(1794475800000) == "2026-11-12T09:30:00+00:00"


def test_posted_at_rejects_invalid_values():
    assert normalize_posted_at("not-a-date") is None


def test_recruitee_job_extraction(monkeypatch):
    payload = {
        "offers": [{
            "id": 123,
            "title": "Data Engineer",
            "description": "Build data pipelines",
            "location": "Bengaluru, India",
            "careers_apply_url": "https://acme.recruitee.com/o/data-engineer",
            "published_at": "2026-11-13T10:00:00Z",
        }]
    }

    def handler(request):
        assert request.url.host == "acme.recruitee.com"
        return httpx.Response(200, json=payload, request=request)


    boards = [
        BoardSource(provider="recruitee", slug="acme", company_name="Acme"),
    ]
    import app.discovery as discovery_module
    original_client = discovery_module.httpx.AsyncClient

    def mocked_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(discovery_module.httpx, "AsyncClient", mocked_client)
    report = asyncio.run(discovery_module.discover_all_with_report(boards))

    assert report.board_job_counts == {
        ("recruitee", "acme"): 1,
    }
    assert report.boards_checked == 1
    assert report.boards_succeeded == 1
    assert report.boards_failed == 0
    assert report.jobs[0].source == "recruitee"
    assert report.jobs[0].title == "Data Engineer"
    assert report.jobs[0].country == "India"
