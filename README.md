# AI Job Hunter

A cloud-first job discovery and application assistant. It discovers listings from supported public job-board feeds, screens them against your preferences, stores them persistently and can notify you through Telegram.

## Current features
- FastAPI API for preferences, job ingestion, discovery and monitoring status
- SQLAlchemy persistence for preferences, registered boards, jobs and notification delivery attempts
- PostgreSQL for Docker deployments and SQLite for local development
- Greenhouse and Lever public job-board read adapters (a company board slug is required)
- Celery worker + Celery Beat scheduler backed by Redis
- Configurable discovery interval (default: every 120 seconds; minimum: 60 seconds)
- Telegram alerts for new matched/review jobs, with retry on later cycles if delivery fails
- Duplicate listing protection and explainable screening rules
- Pytest tests for screening and Telegram alert formatting

## Target profile defaults
- Markets: India, USA and other international markets
- Preferred location: Bangalore; remote roles can be included
- India minimum CTC: ₹15 LPA
- Role families: software/backend, Python, AI/ML, data analytics/engineering, privacy, governance, automation/RPA, DevOps and cybersecurity

## Run locally with Docker
1. Copy `.env.example` to `.env`.
2. Add your Telegram bot token and chat ID (instructions below).
3. Run `docker compose up --build -d`.
4. Open `http://localhost:8000/docs`.
5. Register a Greenhouse or Lever board using `POST /api/v1/sources/boards`.
6. Check `GET /api/v1/monitoring/status` and trigger a one-off scan with `POST /api/v1/discovery/run`.

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
- `GET/PUT /api/v1/preferences` — candidate filters
- `POST /api/v1/sources/boards` — register a Greenhouse or Lever board
- `POST /api/v1/discovery/run` — run a scan immediately
- `GET /api/v1/jobs` — list discovered jobs
- `GET /api/v1/monitoring/status` — counts and Telegram/scheduler configuration status
- `POST /api/v1/notifications/telegram/test` — send a test alert

## Discovery coverage and latency
The starter's two-minute schedule applies only to registered Greenhouse/Lever boards. It is not a universal search index and cannot guarantee detection at the instant a role is published. Other sources (including LinkedIn, Naukri and Indeed) must be connected through permitted APIs, approved data providers or user-authorized flows. Polling frequency must respect each source's terms and rate limits.

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
This is an active development project, not yet production-ready. Authentication, database migrations, cloud deployment, source health monitoring, secure candidate profile storage, resume intelligence, the React dashboard and supported application workflows remain future milestones.
