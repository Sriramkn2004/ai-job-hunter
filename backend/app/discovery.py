from dataclasses import dataclass, field
from datetime import datetime, timezone
import re

import httpx
import hashlib
from app.schemas import BoardSource, JobIn



def infer_country(location: str) -> str:
    """Infer a country only from explicit country names or known Indian city names."""
    value = (location or "").strip().lower()
    if not value:
        return ""

    explicit_countries = {
        "india": "India",
        "united states of america": "USA",
        "united states": "USA",
        "usa": "USA",
        "u.s.a.": "USA",
        "united kingdom": "UK",
        "canada": "Canada",
        "australia": "Australia",
        "germany": "Germany",
        "singapore": "Singapore",
    }
    for country_name, country_code in explicit_countries.items():
        pattern = rf"(?<![a-z]){re.escape(country_name)}(?![a-z])"
        if re.search(pattern, value):
            return country_code

    indian_cities = (
        "bangalore", "bengaluru", "hyderabad", "chennai", "mumbai",
        "pune", "gurugram", "gurgaon", "noida", "new delhi", "delhi",
        "kolkata", "ahmedabad", "kochi", "thiruvananthapuram",
    )
    for city in indian_cities:
        pattern = rf"(?<![a-z]){re.escape(city)}(?![a-z])"
        if re.search(pattern, value):
            return "India"
    return ""


def normalize_posted_at(value) -> str | None:
    """Normalize source posting timestamps to UTC ISO-8601 without inventing dates."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)) or str(value).strip().isdigit():
            timestamp = float(value)
            if timestamp > 10_000_000_000:  # millisecond epoch (e.g. Lever)
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError, OSError):
        return None


GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
LEVER_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"
ASHBY_URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
RECRUITEE_URL = "https://{slug}.recruitee.com/api/offers/"
WORKABLE_URL = "https://www.workable.com/api/accounts/{slug}?details=true"
SMARTRECRUITERS_URL = "https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset=0&destination=PUBLIC"
REMOTEOK_URL = "https://remoteok.com/api"

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
                    posted_at=normalize_posted_at(row.get("first_published")),
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
                    posted_at=normalize_posted_at(row.get("createdAt")),
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
                    posted_at=normalize_posted_at(row.get("publishedAt")),
                    apply_url=row.get("applyUrl") or job_url,
                )
            )

        return jobs

    if board.provider == "smartrecruiters":
        # The list endpoint returns summaries; fetch each public posting detail
        # to obtain its real application URL and description.
        jobs = []
        offset = 0
        page_size = 100
        total_found = None
        while total_found is None or offset < total_found:
            response = await client.get(
                SMARTRECRUITERS_URL.format(slug=board.slug).replace(
                    "limit=100&offset=0", f"limit={page_size}&offset={offset}"
                ),
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("SmartRecruiters returned an invalid postings response")
            rows = payload.get("content", [])
            if not isinstance(rows, list):
                raise ValueError("SmartRecruiters returned an invalid postings list")
            total_found = int(payload.get("totalFound", offset + len(rows)))
            if not rows:
                break

            for row in rows:
                if not isinstance(row, dict) or not row.get("id"):
                    continue
                detail_response = await client.get(
                    f"https://api.smartrecruiters.com/v1/companies/{board.slug}/postings/{row['id']}",
                    timeout=20,
                )
                detail_response.raise_for_status()
                detail = detail_response.json()
                if not isinstance(detail, dict):
                    continue
                location_data = detail.get("location") or row.get("location") or {}
                if isinstance(location_data, dict):
                    city = location_data.get("city") or ""
                    region = location_data.get("region") or ""
                    country_name = location_data.get("country") or ""
                    location = ", ".join(
                        part for part in (city, region, country_name) if part
                    )
                    country_codes = {
                        "in": "India", "us": "USA", "gb": "UK", "uk": "UK",
                        "ca": "Canada", "au": "Australia", "de": "Germany",
                        "sg": "Singapore",
                    }
                    country = country_codes.get(str(country_name).lower(), "")
                else:
                    location = str(location_data)
                    country = ""
                country = country or infer_country(location)
                job_ad = detail.get("jobAd") or {}
                sections = job_ad.get("sections") or {} if isinstance(job_ad, dict) else {}
                description = "\\n\\n".join(
                    str(section.get("text") or "")
                    for section in sections.values()
                    if isinstance(section, dict) and section.get("text")
                )
                apply_url = detail.get("applyUrl") or detail.get("jobAdUrl")
                if not apply_url:
                    continue
                employment = detail.get("typeOfEmployment") or {}
                jobs.append(JobIn(
                    source="smartrecruiters",
                    source_job_id=f"smartrecruiters:{board.slug}:{row['id']}",
                    company=(detail.get("company") or {}).get("name") or board.company_name,
                    title=detail.get("name") or row.get("name") or "Untitled",
                    description=description,
                    location=location,
                    country=country,
                    employment_type=employment.get("label") if isinstance(employment, dict) else None,
                    posted_at=normalize_posted_at(detail.get("releasedDate") or row.get("releasedDate")),
                    apply_url=apply_url,
                ))
            offset += len(rows)
            if len(rows) < page_size:
                break
        return jobs

    if board.provider == "workable":
        response = await client.get(
            WORKABLE_URL.format(slug=board.slug),
            timeout=25,
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("jobs", []) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            raise ValueError("Workable returned an invalid jobs list")
        jobs = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            shortcode = row.get("shortcode") or row.get("id")
            if not shortcode:
                continue
            location_data = row.get("location") or {}
            if isinstance(location_data, dict):
                location = location_data.get("location_str") or ", ".join(
                    str(part) for part in (
                        location_data.get("city"),
                        location_data.get("region"),
                        location_data.get("country"),
                    ) if part
                )
                country = location_data.get("country") or location_data.get("country_code") or ""
            else:
                location = str(location_data)
                country = row.get("country") or ""
            country_codes = {
                "IN": "India", "US": "USA", "GB": "UK", "UK": "UK",
                "CA": "Canada", "AU": "Australia", "DE": "Germany", "SG": "Singapore",
            }
            country = country_codes.get(str(country).upper(), country) or infer_country(location)
            salary = row.get("salary") or {}
            jobs.append(JobIn(
                source="workable",
                source_job_id=f"workable:{board.slug}:{shortcode}",
                company=(payload.get("name") if isinstance(payload, dict) else None) or board.company_name,
                title=row.get("title") or row.get("name") or "Untitled",
                description=row.get("description") or "",
                location=location,
                country=country,
                employment_type=row.get("employment_type"),
                salary_min=salary.get("salary_from") if isinstance(salary, dict) else None,
                salary_max=salary.get("salary_to") if isinstance(salary, dict) else None,
                salary_currency=(salary.get("salary_currency") or "").upper() if isinstance(salary, dict) and salary.get("salary_currency") else None,
                posted_at=normalize_posted_at(row.get("published_on") or row.get("created_at")),
                apply_url=row.get("application_url") or row.get("url") or row.get("shortlink"),
            ))
        return jobs

    if board.provider == "remoteok":
        response = await client.get(REMOTEOK_URL, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Remote OK returned an invalid jobs list")
        jobs = []
        for row in payload:
            if not isinstance(row, dict) or not row.get("id") or not row.get("position"):
                continue
            apply_url = row.get("url") or row.get("apply_url")
            if not apply_url:
                continue
            location = row.get("location") or ""
            jobs.append(JobIn(
                source="remoteok",
                source_job_id=f"remoteok:{row['id']}",
                company=row.get("company") or board.company_name,
                title=row.get("position") or "Untitled",
                description=row.get("description") or "",
                location=location,
                country=infer_country(location),
                posted_at=normalize_posted_at(row.get("date")),
                apply_url=apply_url,
            ))
        return jobs

    if board.provider == "recruitee":
        response = await client.get(
            RECRUITEE_URL.format(slug=board.slug),
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("offers", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError("Recruitee returned an invalid offers list")

        jobs = []
        for row in rows:
            if not isinstance(row, dict) or row.get("id") is None:
                continue
            location = row.get("location") or ""
            if isinstance(location, dict):
                location = location.get("city") or location.get("name") or ""
            apply_url = row.get("careers_apply_url") or row.get("careers_url") or row.get("url")
            if not apply_url:
                continue
            jobs.append(
                JobIn(
                    source="recruitee",
                    source_job_id=f"recruitee:{board.slug}:{row['id']}",
                    company=board.company_name,
                    title=row.get("title") or row.get("name") or "Untitled",
                    description=row.get("description") or row.get("description_html") or "",
                    location=str(location),
                    country=infer_country(str(location)),
                    employment_type=row.get("employment_type"),
                    posted_at=normalize_posted_at(
                        row.get("published_at") or row.get("created_at")
                    ),
                    apply_url=apply_url,
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
