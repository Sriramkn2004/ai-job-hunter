# Development roadmap

- [x] FastAPI service skeleton and health endpoint
- [x] Configurable candidate preferences and expanded role families
- [x] Greenhouse and Lever read-only discovery adapters
- [x] Explainable screening rules and duplicate detection
- [x] SQLAlchemy persistence for preferences, company boards and jobs
- [x] PostgreSQL Docker configuration and SQLite local-development fallback
- [x] API test proving jobs can be read back from persistent storage
- [x] Celery worker and Celery Beat scheduled discovery (default 120-second interval)
- [x] Telegram alert formatting, delivery, retry tracking and test endpoint
- [x] Monitoring status endpoint
- [ ] Alembic schema migrations
- [ ] Source health metrics, per-source retry/backoff and more permitted source adapters
- [ ] Telegram inline approval callbacks
- [ ] Resume upload, parsing and structured candidate profile
- [x] AI-assisted truthful resume tailoring and interview preparation (requires user-provided OpenAI API key)
- [x] Human-in-the-loop application review and manual outcome tracking\n- [ ] Authorized employer-specific application submission adapters (provider/API access required)
- [ ] React dashboard, job details, skipped reasons and analytics
- [ ] Multi-user authentication and tenant isolation\n- [ ] Cloud deployment, production secrets management, monitoring and backups

## Production release gates
Before enabling production applications: add authentication and authorization, encrypt sensitive profile/resume data, introduce migrations, prevent duplicate submissions, require explicit confirmation for sensitive declarations, validate destination domains, and capture verifiable submission confirmations.
