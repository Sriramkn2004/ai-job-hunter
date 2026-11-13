import httpx
from app.schemas import BoardSource, JobIn

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
LEVER_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"

async def discover_board(client: httpx.AsyncClient, board: BoardSource) -> list[JobIn]:
    if board.provider == "greenhouse":
        response = await client.get(GREENHOUSE_URL.format(slug=board.slug), timeout=20)
        response.raise_for_status()
        rows = response.json().get("jobs", [])
        return [
            JobIn(
                source="greenhouse",
                source_job_id=f"greenhouse:{row['id']}",
                company=board.company_name,
                title=row.get("title", "Untitled"),
                description=row.get("content", "") or "",
                location=(row.get("location") or {}).get("name", ""),
                apply_url=row.get("absolute_url"),
            )
            for row in rows
        ]

    if board.provider == "lever":
        response = await client.get(LEVER_URL.format(slug=board.slug), timeout=20)
        response.raise_for_status()
        rows = response.json()
        jobs = []
        for row in rows:
            categories = row.get("categories") or {}
            jobs.append(JobIn(
                source="lever",
                source_job_id=f"lever:{row['id']}",
                company=board.company_name,
                title=row.get("text", "Untitled"),
                description=row.get("descriptionPlain", "") or "",
                location=categories.get("location", ""),
                employment_type=categories.get("commitment"),
                apply_url=row.get("hostedUrl") or row.get("applyUrl"),
            ))
        return jobs

    return []

async def discover_all(boards: list[BoardSource]) -> list[JobIn]:
    async with httpx.AsyncClient(
        headers={"User-Agent": "AIJobHunter/0.1 (personal job search)"}
    ) as client:
        jobs = []
        for board in boards:
            try:
                jobs.extend(await discover_board(client, board))
            except httpx.HTTPError:
                # Isolate source failures so one board cannot stop the rest.
                continue
        return jobs
