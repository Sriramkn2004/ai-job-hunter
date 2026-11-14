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
            "apply_url": "https://employer.example/apply/101",
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
    # Remote OK requires a followed link to its canonical listing.
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
    assert jobs[0].description == "Build data pipelines\n\nPython and SQL"
    assert jobs[0].posted_at == "2026-11-12T08:30:00+00:00"
    assert str(jobs[0].apply_url) == "https://www.smartrecruiters.com/Acme/202"

def test_workable_public_careers_feed_extraction():
    payload = {
        "name": "Acme Technologies",
        "jobs": [
            {
                "shortcode": "PY123",
                "title": "Python Developer",
                "description": "Build backend services",
                "published_on": "2026-11-13T10:00:00Z",
                "employment_type": "Full-time",
                "application_url": "https://apply.workable.com/acme/j/PY123/",
                "url": "https://apply.workable.com/acme/j/PY123",
                "location": {
                    "location_str": "Bengaluru, Karnataka, India",
                    "country_code": "IN",
                    "telecommuting": False,
                },
                "salary": {
                    "salary_from": 1500000,
                    "salary_to": 2200000,
                    "salary_currency": "inr",
                },
            }
        ],
    }

    def handler(request):
        assert request.url.host == "www.workable.com"
        assert request.url.path == "/api/accounts/acme"
        assert request.url.params["details"] == "true"
        return httpx.Response(200, json=payload, request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            board = BoardSource(provider="workable", slug="acme", company_name="Acme")
            return await discover_board(client, board)

    jobs = asyncio.run(run())
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "workable:acme:PY123"
    assert jobs[0].company == "Acme Technologies"
    assert jobs[0].title == "Python Developer"
    assert jobs[0].country == "India"
    assert jobs[0].salary_min == 1500000
    assert jobs[0].salary_max == 2200000
    assert jobs[0].salary_currency == "INR"
    assert jobs[0].posted_at == "2026-11-13T10:00:00+00:00"
    assert str(jobs[0].apply_url) == "https://apply.workable.com/acme/j/PY123/"

def test_personio_public_xml_feed_extraction():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <workzag-jobs>
      <position>
        <id>987</id>
        <name>Backend Engineer</name>
        <office>Bengaluru, India</office>
        <department>Engineering</department>
        <employmentType>permanent</employmentType>
        <createdAt>2026-11-12T09:00:00+00:00</createdAt>
        <jobDescriptions>
          <jobDescription>
            <name>Your tasks</name>
            <value><![CDATA[Build reliable APIs.]]></value>
          </jobDescription>
          <jobDescription>
            <name>Requirements</name>
            <value><![CDATA[Python and SQL experience.]]></value>
          </jobDescription>
        </jobDescriptions>
      </position>
    </workzag-jobs>
    """

    def handler(request):
        assert request.url.host == "acme.jobs.personio.de"
        assert request.url.path == "/xml"
        assert request.url.params["language"] == "en"
        return httpx.Response(200, text=xml, request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            board = BoardSource(provider="personio", slug="acme", company_name="Acme")
            return await discover_board(client, board)

    jobs = asyncio.run(run())
    assert len(jobs) == 1
    assert jobs[0].source_job_id == "personio:acme:987"
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].country == "India"
    assert jobs[0].employment_type == "permanent"
    assert jobs[0].posted_at == "2026-11-12T09:00:00+00:00"
    assert "Build reliable APIs." in jobs[0].description
    assert str(jobs[0].apply_url) == "https://acme.jobs.personio.de/job/987"
