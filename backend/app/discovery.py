from dataclasses import dataclass, field

import httpx
import hashlib
from app.schemas import BoardSource, JobIn



def infer_country(location: str) -> str:
    """Infer country only from explicit country names or common Indian cities."""
    value = (location or "").strip().lower()
    if not value:
        return ""

    explicit_countries = {
        "india": "India",
        "united states": "USA",
        "united states of america": "USA",
        "usa": "USA",
        "united kingdom": "UK",
        "canada": "Canada",
        "australia": "Australia",
        "germany": "Germany",
        "singapore": "Singapore",
    }
    for country_name, country_code in explicit_countries.items():
        if country_name in value:
            return country_code

    indian_cities = (
        "bangalore", "bengaluru", "hyderabad", "chennai", "mumbai",
        "pune", "gurugram", "gurgaon", "noida", "new delhi", "delhi",
        "kolkata", "ahmedabad", "kochi", "thiruvananthapuram",
    )
    if any(city in value for city in indian_cities):
        return "India"

    return ""


GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
LEVER_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"
ASHBY_URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"

@dataclass
class DiscoveryFailure:
    provider: str
    slug: str
    company: str
    error: str


@dataclass
class DiscoveryReport:
    boards_checked: int = 0
    boards_succeeded: int = 0
    boards_failed: int = 0
    jobs: list[JobIn] = field(default_factory=list)
    failures: list[DiscoveryFailure] = field(default_factory=list)


async def discover_board(
    client: httpx.AsyncClient,
    board: BoardSource,
) -> list[JobIn]:

    if board.provider == "greenhouse":
        response = await client.get(
            GREENHOUSE_URL.format(slug=board.slug),
            timeout=20,
        )
        response.raise_for_status()

        payload = response.json()
        rows = payload.get("jobs", [])

        if not isinstance(rows, list):
            raise ValueError("Greenhouse returned an invalid jobs list")

        jobs = []

        for row in rows:
            if not isinstance(row, dict) or "id" not in row:
                continue

            location = row.get("location") or {}

            jobs.append(
                JobIn(
                    source="greenhouse",
                    source_job_id=f"greenhouse:{row['id']}",
                    company=board.company_name,
                    title=row.get("title", "Untitled"),
                    description=row.get("content", "") or "",
                    location=location.get("name", "")
                    if isinstance(location, dict)
                    else "",
                    country=infer_country(location.get("name", "") if isinstance(location, dict) else ""),
                    apply_url=row.get("absolute_url"),
                )
            )

        return jobs

    if board.provider == "lever":
        response = await client.get(
            LEVER_URL.format(slug=board.slug),
            timeout=20,
        )
        response.raise_for_status()

        rows = response.json()

        if not isinstance(rows, list):
            raise ValueError("Lever returned an invalid jobs list")

        jobs = []

        for row in rows:
            if not isinstance(row, dict) or "id" not in row:
                continue

            categories = row.get("categories") or {}
            if not isinstance(categories, dict):
                categories = {}

            jobs.append(
                JobIn(
                    source="lever",
                    source_job_id=f"lever:{row['id']}",
                    company=board.company_name,
                    title=row.get("text", "Untitled"),
                    description=row.get("descriptionPlain", "") or "",
                    location=categories.get("location", ""),
                    country=infer_country(categories.get("location", "")),
                    employment_type=categories.get("commitment"),
                    apply_url=row.get("hostedUrl") or row.get("applyUrl"),
                )
            )

        return jobs
    if board.provider == "ashby":
        response = await client.get(
            ASHBY_URL.format(slug=board.slug),
            timeout=20,
        )
        response.raise_for_status()

        payload = response.json()
        rows = payload.get("jobs", [])

        if not isinstance(rows, list):
            raise ValueError("Ashby returned an invalid jobs list")

        jobs = []

        for row in rows:
            if not isinstance(row, dict):
                continue

            job_url = row.get("jobUrl") or row.get("applyUrl")
            if not job_url:
                continue

            raw_id = row.get("id")
            stable_id = str(raw_id) if raw_id else hashlib.sha256(
                job_url.encode("utf-8")
            ).hexdigest()

            address = row.get("address") or {}
            postal = address.get("postalAddress") or {}
            if not isinstance(postal, dict):
                postal = {}

            location = row.get("location", "")
            country = postal.get("addressCountry", "")

            jobs.append(
                JobIn(
                    source="ashby",
                    source_job_id=f"ashby:{stable_id}",
                    company=board.company_name,
                    title=row.get("title", "Untitled"),
                    description=row.get("descriptionPlain", "") or "",
                    location=location,
                    country=country,
                    employment_type=row.get("employmentType"),
                    posted_at=row.get("publishedAt"),
                    apply_url=row.get("applyUrl") or job_url,
                )
            )

        return jobs
    raise ValueError(f"Unsupported job board provider: {board.provider}")


async def discover_all_with_report(
    boards: list[BoardSource],
) -> DiscoveryReport:

    report = DiscoveryReport(boards_checked=len(boards))

    async with httpx.AsyncClient(
        headers={"User-Agent": "AIJobHunter/0.1 (personal job search)"}
    ) as client:

        for board in boards:
            try:
                jobs = await discover_board(client, board)
                report.jobs.extend(jobs)
                report.boards_succeeded += 1

            except (
                httpx.HTTPError,
                ValueError,
                KeyError,
                TypeError,
                AttributeError,
            ) as exc:
                report.boards_failed += 1

                report.failures.append(
                    DiscoveryFailure(
                        provider=board.provider,
                        slug=board.slug,
                        company=board.company_name,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )

    return report


async def discover_all(boards: list[BoardSource]) -> list[JobIn]:
    # Keep the original interface for existing callers.
    report = await discover_all_with_report(boards)
    return report.jobs
