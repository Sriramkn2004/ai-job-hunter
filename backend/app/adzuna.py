import hashlib
import os

import httpx

from app.schemas import JobIn


ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"


class AdzunaConfigurationError(Exception):
    pass


async def discover_adzuna(
    country: str,
    what: str,
    where: str = "",
) -> list[JobIn]:
    app_id = os.getenv("ADZUNA_APP_ID", "").strip()
    app_key = os.getenv("ADZUNA_APP_KEY", "").strip()

    if not app_id or not app_key:
        raise AdzunaConfigurationError(
            "Adzuna credentials are not configured"
        )

    country = country.lower().strip()

    if country not in {"in", "us"}:
        raise ValueError(f"Unsupported Adzuna country: {country}")

    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": 50,
        "what": what,
        "where": where,
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(
        headers={"User-Agent": "AIJobHunter/0.1 (personal job search)"}
    ) as client:
        response = await client.get(
            ADZUNA_URL.format(country=country),
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

    rows = payload.get("results", [])

    if not isinstance(rows, list):
        raise ValueError("Adzuna returned an invalid results list")

    jobs = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        raw_id = row.get("id")
        redirect_url = row.get("redirect_url")

        if not raw_id or not redirect_url:
            continue

        location_data = row.get("location") or {}
        company_data = row.get("company") or {}

        location = (
            location_data.get("display_name", "")
            if isinstance(location_data, dict)
            else ""
        )
        company = (
            company_data.get("display_name", "Unknown company")
            if isinstance(company_data, dict)
            else "Unknown company"
        )

        currency = "INR" if country == "in" else "USD"

        jobs.append(
            JobIn(
                source="adzuna",
                source_job_id=f"adzuna:{country}:{raw_id}",
                company=company,
                title=row.get("title", "Untitled"),
                description=row.get("description", "") or "",
                location=location,
                country="India" if country == "in" else "USA",
                employment_type=row.get("contract_type"),
                salary_min=row.get("salary_min"),
                salary_max=row.get("salary_max"),
                salary_currency=currency,
                salary_period=(
                    "year"
                    if row.get("salary_min") is not None or row.get("salary_max") is not None
                    else None
                ),
                posted_at=row.get("created"),
                apply_url=redirect_url,
            )
        )

    return jobs

