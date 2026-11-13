# Development roadmap

- [x] FastAPI service skeleton and health endpoint
- [x] Configurable candidate preferences and expanded role families
- [x] Greenhouse and Lever read-only discovery adapters
- [x] Explainable screening rules and duplicate detection
- [x] SQLAlchemy persistence for preferences, company boards and jobs
- [x] PostgreSQL Docker configuration and SQLite local-development fallback
- [x] API test proving jobs can be read back from persistent storage
- [ ] Alembic schema migrations
- [ ] Redis/Celery scheduled discovery workers, retries and source health metrics
- [ ] More permitted source adapters and company-board registry
- [ ] Telegram notifications with secure approval callbacks
- [ ] Resume upload, parsing and structured candidate profile
- [ ] AI-assisted truthful resume tailoring and answer drafting
- [ ] Human-in-the-loop application review and supported submission adapters
- [ ] React dashboard, job details, skipped reasons and analytics
- [ ] Cloud deployment, authentication, secrets management, monitoring and backups

## Production release gates
Before enabling production applications: add authentication and authorization, encrypt sensitive profile/resume data, introduce migrations, prevent duplicate submissions, require explicit confirmation for sensitive declarations, validate destination domains, and capture verifiable submission confirmations.
