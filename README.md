# AI Job Hunter

A cloud-first job discovery and application assistant. It discovers listings from supported public job-board feeds, screens them against your preferences, stores them persistently and can notify you through Telegram.

## Current features
- FastAPI API for preferences, job ingestion, discovery, curated source catalog and monitoring
- SQLAlchemy persistence for preferences, registered boards, per-board health, jobs and notification delivery attempts
- PostgreSQL for Docker deployments and SQLite for local development
- Greenhouse, Lever, Ashby, Recruitee, SmartRecruiters, Workable and Personio public company-board adapters, plus Remote OK's public feed (enabled automatically)
- Celery worker + Celery Beat scheduler backed by Redis
- Configurable discovery interval (default: every 120 seconds; minimum: 60 seconds)
- Telegram alerts for new matched/review jobs, with retry on later cycles if delivery fails
- Duplicate listing protection and explainable screening rules
- Curated employer directory with live-feed-checked, duplicate-safe imports
- Per-board health history: last check, last success, jobs found and consecutive failures\n- Pytest coverage for screening, provider adapters, source imports and monitoring

## Target profile defaults
- Markets: India, USA and other international markets
- Preferred location: Bangalore; remote roles can be included
- India minimum CTC: ₹15 LPA
- Role families: software/backend, Python, AI/ML, data analytics/engineering, privacy, governance, automation/RPA, DevOps and cybersecurity

## Run locally with Docker
1. Copy `.env.example` to `.env`.
2. Add your Telegram bot token and chat ID (instructions below).
3. Run `docker compose up --build -d`.
4. Open the dashboard at `http://localhost:3000` and API docs at `http://localhost:8000/docs`.
5. Browse the curated employer directory with `GET /api/v1/sources/catalog`; import selected entries with `POST /api/v1/sources/catalog/import`, which rechecks each live feed before saving.
6. Validate public company-board feeds with `POST /api/v1/sources/boards/validate` before registering them; validation reports live listing counts and does not save anything.
7. Register one or more company boards using `POST /api/v1/sources/boards` or bulk import using `POST /api/v1/sources/boards/bulk`.
8. List and manage registered boards with `GET` and `DELETE /api/v1/sources/boards`.
9. Check `GET /api/v1/monitoring/status` and trigger a one-off scan with `POST /api/v1/discovery/run`.

The worker and scheduler are separate services. They continue running when your laptop is off only after the Docker stack is deployed to an always-on cloud host.

## Configure Telegram
1. In Telegram, message **@BotFather**, run `/newbot`, and follow its steps.
2. Copy the bot token into `TELEGRAM_BOT_TOKEN` in your private `.env` file.
3. Open your new bot and press **Start** (or send `/start`).
4. In a private browser window, open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`. Find `message.chat.id` in the response and put that value in `TELEGRAM_CHAT_ID`.
5. Restart the stack, then call `POST /api/v1/notifications/telegram/test` from the API docs.
6. Never commit `.env`, bot tokens, chat IDs or resume files to GitHub. Rotate the bot token with BotFather if it is exposed.

## API endpoints
- `GET /health` — API health
- Dashboard — `http://localhost:3000` (served by Nginx and proxied to the API)
- `GET/PUT /api/v1/preferences` — candidate filters
- `GET /api/v1/sources/catalog` — view the curated employer board directory
- `POST /api/v1/sources/catalog/import` — live-check and import selected curated boards (body requires only `provider` and `slug`)
- `POST /api/v1/sources/boards` — register one company board (idempotent)
- `POST /api/v1/sources/boards/bulk` — register up to 100 company boards in one request; duplicate entries are skipped
- `POST /api/v1/sources/boards/validate` — test up to 25 public company-board feeds, report each live job count and errors, and save nothing
- `GET /api/v1/sources/boards` — list registered boards
- `DELETE /api/v1/sources/boards/{board_id}` — remove a board from scheduled monitoring
- `POST /api/v1/discovery/run` — run a scan immediately
- `GET /api/v1/jobs` — search and page through jobs using `q`, `status`, `country`, `company`, `source`, `limit` and `offset`
- `GET /api/v1/monitoring/status` — counts and Telegram/scheduler configuration status
- `GET /api/v1/monitoring/boards` — per-board check history, job counts and failure status
- `POST /api/v1/notifications/telegram/test` — send a test alert

## Discovery coverage and latency
The starter's two-minute schedule applies only to registered Greenhouse/Lever/Ashby/Recruitee/SmartRecruiters/Workable/Personio company boards and the Remote OK feed. It is not a universal search index and cannot guarantee detection at the instant a role is published. Other sources (including LinkedIn, Naukri and Indeed) must be connected through permitted APIs, approved data providers or user-authorized flows. Polling frequency must respect each source's terms and rate limits.

## Application safety
This milestone only discovers and alerts; it does not submit applications. Future application workflows must not bypass access controls or CAPTCHAs, must not invent candidate information, and must request confirmation for legal declarations, work authorization, demographic information and consent. A job must only be marked applied after a verifiable destination confirmation.

## Local development without Docker
```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Run tests from `backend` with `python -m pytest -q`.

## Project status
This is an active development project, not yet production-ready. Authentication, database migrations, cloud deployment, secure candidate profile storage, resume intelligence and supported application workflows remain future milestones. Source health monitoring is implemented but still needs broader operational testing.
