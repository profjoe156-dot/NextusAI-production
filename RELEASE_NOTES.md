# NexusAI Release Notes

## Release status

This repository is a **deployment-ready production baseline** for NexusAI. It includes the FastAPI web service, Telegram webhook dispatcher, scheduler worker, PostgreSQL schema and migrations, Redis controls, OpenAI chat integration, administrator dashboard, Docker/Compose configuration, Railway manifests, tests, CI, and operational documentation.

Actual production deployment is intentionally not performed because it requires the owner’s Telegram, OpenAI, payment-provider, Railway, database, Redis, domain, and administrator credentials.

## Delivered systems

| System | Status |
|---|---|
| Telegram onboarding and inline menu | Complete |
| OpenAI chat, history, quotas, and rate limiting | Complete |
| AI tool directory and seed content | Complete |
| Prompt library and premium access rules | Complete |
| AI news feed ingestion and scheduled refresh | Complete |
| User registration and account views | Complete |
| Referral attribution and exactly-once rewards | Complete |
| Premium grants, expiry, and optional Telegram invoices | Complete |
| Authenticated administrator dashboard and APIs | Complete |
| PostgreSQL migration and async repositories | Complete |
| Redis rate limiting, caching, and worker locks | Complete |
| Health, Prometheus metrics, request IDs, and structured logs | Complete |
| Docker, Compose, Railway web/worker manifests, and CI | Complete |
| Installation, deployment, architecture, and operations guides | Complete |

## Final validation

The release gate completed successfully with **15 passing tests**. Ruff formatting and linting passed, MyPy static analysis passed, Alembic successfully completed upgrade → downgrade → upgrade against a clean isolated database, and the deployment artifact validator passed.

The sandbox did not provide a Docker daemon, so the production image was not built locally during final verification. The included GitHub Actions workflow performs the Docker build in CI, and `scripts/validate_deployment.py` statically validates the Dockerfile, Compose topology, Railway manifests, and required environment surface.

## Deployment handoff

Start with [`README.md`](README.md), then follow [`docs/RAILWAY.md`](docs/RAILWAY.md). Generate all production secrets, provision managed PostgreSQL and Redis, deploy web and worker services, seed initial content, set the final public URL, and complete the verification checklist before inviting users.
