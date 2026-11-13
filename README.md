# AI Job Hunter

A cloud-first job discovery and application assistant. This project starts with normalized job ingestion, configurable screening, a review queue, and read-only integrations for supported public job boards.

## Current features
- FastAPI API with health, preferences, board registration, job ingestion, discovery and approval-preparation endpoints
- SQLAlchemy persistence for preferences, registered boards and discovered jobs
- PostgreSQL for Docker deployments and SQLite for local development
- Greenhouse and Lever public job-board read adapters (a company board slug is required)
- Standardized job records and database-level duplicate protection
- Configurable markets, roles, preferred locations and India salary threshold
- Explainable screening; undisclosed salary is never assumed to meet the threshold
- Docker Compose with API, PostgreSQL and Redis
- Pytest unit and API persistence tests

## Target profile defaults
- Markets: India, USA and other international markets
- Preferred location: Bangalore; remote roles can be included
- India minimum CTC: ₹15 LPA
- Hybrid workflow: eligible high-confidence matches can be prepared automatically; uncertain or incomplete cases go to review
- Role families: software/backend, Python, AI/ML, data analytics/engineering, privacy, governance, automation/RPA, DevOps and cybersecurity

## Quick start with Docker
1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. Open `http://localhost:8000/docs`.
4. Register a Greenhouse or Lever board using `POST /api/v1/sources/boards`.
5. Trigger discovery using `POST /api/v1/discovery/run`.

## Local development without Docker
```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# SQLite is the default when DATABASE_URL is not set.
uvicorn app.main:app --reload
```

Run tests from the `backend` directory with `python -m pytest -q`.

## Important safety and reliability boundaries
- The public board adapters are read-only discovery sources, not universal search engines; each board requires a company slug.
- LinkedIn, Naukri, Indeed and other sources must use permitted APIs, partnerships or user-authorized workflows. Do not bypass access controls or CAPTCHAs.
- Never invent candidate skills, qualifications, experience or application answers.
- Legal declarations, work authorization, demographic information and consent require explicit user confirmation.
- An application is not considered submitted until the destination provides a verifiable confirmation.
- This is an active development project, not yet production-ready. Authentication, migrations, scheduled workers, monitoring, secure file handling and source-specific application adapters remain on the roadmap.

## Roadmap
See [docs/ROADMAP.md](docs/ROADMAP.md).

## Development history
The project is developed through genuine, incremental commits as features are implemented and tested. No fabricated or backdated commits.
