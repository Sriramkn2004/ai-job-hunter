# AI Job Hunter

A cloud-first job discovery and application assistant. This repository starts with normalized job ingestion, configurable screening, and a review queue.

## Initial features
- FastAPI API with health, preferences, board registration, job ingestion and discovery
- Greenhouse and Lever public job-board read adapters (company board slug required)
- Standardized job records and duplicate detection
- Configurable markets, roles, location and India salary threshold
- Explainable screening; undisclosed salary is never assumed to meet a threshold
- Docker Compose with API, PostgreSQL and Redis

## Target profile
- Markets: India, USA and other international markets
- Preferred location: Bangalore (remote can be included)
- India minimum CTC: ₹15 LPA
- Hybrid workflow: clear matches prepared automatically; uncertain cases require review
- Roles: software/backend, Python, AI/ML, data analytics/engineering, privacy, governance, automation/RPA, DevOps and cybersecurity

## Quick start
1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. Open `http://localhost:8000/docs`.
4. Register a Greenhouse or Lever board using `POST /api/v1/sources/boards`.
5. Trigger discovery using `POST /api/v1/discovery/run`.

## Important boundaries
- Public feeds are read-only discovery sources, not universal job search.
- LinkedIn, Naukri, Indeed and other sources must use permitted APIs, partnerships or user-authorized workflows.
- Never invent candidate information or bypass CAPTCHA/access controls.
- Sensitive legal, work authorization, demographic and consent questions require explicit user confirmation.
- This starter uses in-memory storage; PostgreSQL persistence and scheduled workers are upcoming milestones. Do not deploy as production yet.

## Development
See [docs/ROADMAP.md](docs/ROADMAP.md). The project will use genuine incremental commits as features are implemented; no fabricated or backdated history.