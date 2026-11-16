"""Optional AI-assisted career tools and application outcome tracking.

AI calls are made only when OPENAI_API_KEY is configured. Resume content is
provided per request and is not persisted by these endpoints.
"""
import os
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ApplicationOutcomeRecord, ApplicationRecord, JobRecord

router = APIRouter(prefix="/api/v1/career", tags=["career tools"])


class TailorRequest(BaseModel):
    source_job_id: str = Field(min_length=1, max_length=300)
    resume_text: str = Field(min_length=100, max_length=30000)


class InterviewPrepRequest(BaseModel):
    source_job_id: str = Field(min_length=1, max_length=300)
    resume_text: str = Field(default="", max_length=30000)


class OutcomeUpdate(BaseModel):
    outcome: Literal["pending", "interview", "offer", "rejected", "withdrawn", "no_response"]
    interview_stage: str = Field(default="", max_length=120)
    offered_salary: str | None = Field(default=None, max_length=120)
    outcome_notes: str = Field(default="", max_length=4000)


def _job_or_404(db: Session, source_job_id: str) -> JobRecord:
    job = db.scalar(select(JobRecord).where(JobRecord.source_job_id == source_job_id))
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


async def _ask_openai(system_prompt: str, user_prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(503, "AI career tools are not configured. Add OPENAI_API_KEY to your private .env file.")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "temperature": 0.2, "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]},
            )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            raise HTTPException(503, "OpenAI API key was rejected; check OPENAI_API_KEY.")
        raise HTTPException(502, f"AI provider returned HTTP {exc.response.status_code}.")
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        raise HTTPException(502, "Could not generate AI career content. Try again later.")


@router.post("/tailor-resume")
async def tailor_resume(payload: TailorRequest, db: Session = Depends(get_db)):
    job = _job_or_404(db, payload.source_job_id)
    result = await _ask_openai(
        "You are a careful resume editor. Use ONLY facts in the supplied resume. Never invent employers, dates, degrees, metrics, skills, certifications or outcomes. If a requirement is unsupported, label it as a gap. Return: targeted professional summary, reordered relevant skills, rewritten experience bullets, keywords supported by evidence, and gaps to verify. Keep it ATS-readable.",
        f"JOB TITLE: {job.title}\nCOMPANY: {job.company}\nJOB DESCRIPTION:\n{job.description[:12000]}\n\nCANDIDATE RESUME:\n{payload.resume_text}\n\nCreate a tailored draft. Clearly mark every suggested edit for candidate review."
    )
    return {"source_job_id": job.source_job_id, "job_title": job.title, "company": job.company, "review_required": True, "tailored_resume": result}


@router.post("/interview-prep")
async def interview_prep(payload: InterviewPrepRequest, db: Session = Depends(get_db)):
    job = _job_or_404(db, payload.source_job_id)
    result = await _ask_openai(
        "You are an interview coach. Create practical, job-specific preparation. Do not claim the employer will ask these exact questions. Separate technical, behavioral and role/company-context questions. Include concise answer frameworks grounded only in the candidate resume; flag missing experience instead of fabricating it.",
        f"ROLE: {job.title}\nCOMPANY: {job.company}\nJOB DESCRIPTION:\n{job.description[:12000]}\n\nCANDIDATE RESUME (may be empty):\n{payload.resume_text}\n\nProvide 8 likely practice questions, answer guidance, topics to revise, and 3 thoughtful questions to ask the interviewer."
    )
    return {"source_job_id": job.source_job_id, "job_title": job.title, "company": job.company, "practice_only": True, "preparation": result}


@router.put("/applications/{application_id}/outcome")
def update_application_outcome(application_id: int, payload: OutcomeUpdate, db: Session = Depends(get_db)):
    application = db.get(ApplicationRecord, application_id)
    if application is None:
        raise HTTPException(404, "Application not found")
    row = db.scalar(select(ApplicationOutcomeRecord).where(ApplicationOutcomeRecord.application_id == application_id))
    if row is None:
        row = ApplicationOutcomeRecord(application_id=application_id)
        db.add(row)
    for field, value in payload.model_dump().items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return {"application_id": row.application_id, "outcome": row.outcome, "interview_stage": row.interview_stage, "offered_salary": row.offered_salary, "outcome_notes": row.outcome_notes, "updated_at": row.updated_at.isoformat()}


@router.get("/applications/outcomes")
def list_application_outcomes(db: Session = Depends(get_db)):
    rows = db.execute(
        select(ApplicationOutcomeRecord, ApplicationRecord, JobRecord)
        .join(ApplicationRecord, ApplicationOutcomeRecord.application_id == ApplicationRecord.id)
        .join(JobRecord, ApplicationRecord.source_job_id == JobRecord.source_job_id)
        .order_by(ApplicationOutcomeRecord.updated_at.desc())
    ).all()
    return [{
        "application_id": app.id, "company": job.company, "title": job.title,
        "candidate_email": app.candidate_email, "outcome": outcome.outcome,
        "interview_stage": outcome.interview_stage, "offered_salary": outcome.offered_salary,
        "outcome_notes": outcome.outcome_notes, "updated_at": outcome.updated_at.isoformat()
    } for outcome, app, job in rows]
