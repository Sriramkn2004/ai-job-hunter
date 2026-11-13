# Development roadmap

- [x] FastAPI service skeleton and health endpoint
- [x] Preferences schema with target role families
- [x] Greenhouse and Lever read-only discovery adapters
- [x] Explainable screening rules and in-memory duplicate guard
- [ ] PostgreSQL persistence, SQLAlchemy models and migrations
- [ ] Redis/Celery scheduled discovery workers and retries
- [ ] Multi-company board registry and source health metrics
- [ ] Telegram notifications with secure approval callbacks
- [ ] Resume upload, parsing and structured candidate profile
- [ ] AI-assisted truthful resume tailoring and answer drafting
- [ ] Review queue and permitted source-specific application workflows
- [ ] React dashboard, job details, skipped reasons and analytics
- [ ] Cloud deployment, secrets management, monitoring and backups

## Release gates
Before enabling production applications: add authentication, encrypt sensitive profile/resume data, prevent duplicate submissions, require explicit confirmation for sensitive declarations, validate destinations, and capture verifiable submission confirmations.
