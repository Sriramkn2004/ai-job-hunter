from fastapi import FastAPI, HTTPException
from app.schemas import Preferences, JobIn, JobOut, BoardSource
from app.screening import evaluate_job
from app.store import Store

app = FastAPI(title="AI Job Hunter API", version="0.1.0")
store = Store()

@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-job-hunter"}

@app.get("/api/v1/preferences")
def get_preferences():
    return store.preferences.model_dump()

@app.put("/api/v1/preferences")
def update_preferences(payload: Preferences):
    store.preferences = payload
    return payload.model_dump()

@app.post("/api/v1/sources/boards")
def add_board(payload: BoardSource):
    store.boards[(payload.provider, payload.slug)] = payload
    return {"saved": True, "provider": payload.provider, "slug": payload.slug}

@app.post("/api/v1/jobs", response_model=JobOut)
def ingest_job(payload: JobIn):
    existing = store.jobs.get(payload.source_job_id)
    if existing:
        return existing
    result = payload.model_copy(update={"screening": evaluate_job(payload, store.preferences)})
    store.jobs[payload.source_job_id] = result
    return result

@app.get("/api/v1/jobs")
def list_jobs(status: str | None = None):
    jobs = list(store.jobs.values())
    if status:
        jobs = [job for job in jobs if job.screening.status == status]
    return [job.model_dump() for job in jobs]

@app.post("/api/v1/discovery/run")
async def run_discovery():
    from app.discovery import discover_all
    discovered = await discover_all(list(store.boards.values()))
    inserted, duplicates = 0, 0
    for job in discovered:
        if job.source_job_id in store.jobs:
            duplicates += 1
            continue
        screened = job.model_copy(update={"screening": evaluate_job(job, store.preferences)})
        store.jobs[job.source_job_id] = screened
        inserted += 1
    return {"discovered": len(discovered), "inserted": inserted, "duplicates": duplicates}

@app.post("/api/v1/applications/{source_job_id}/approve")
def approve_application(source_job_id: str):
    job = store.jobs.get(source_job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.screening.status not in {"matched", "review"}:
        raise HTTPException(400, "Job is not eligible for approval")
    # This milestone records review approval only. It does not submit externally.
    return {
        "status": "approved_for_preparation",
        "job": job.title,
        "message": "Approval recorded. A permitted source-specific submission adapter is not enabled yet.",
    }
