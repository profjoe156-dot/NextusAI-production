# NexusAI Installation Guide

This guide installs NexusAI either as a complete Docker Compose stack or as a host-based Python application. Docker Compose is the recommended path because it starts PostgreSQL, Redis, the FastAPI web process, and the scheduler worker with consistent versions.

## 1. Collect credentials

Create a Telegram bot with **BotFather** and retain its token. Create an OpenAI API key. For production, prepare an externally reachable HTTPS origin because Telegram sends bot updates to an HTTPS webhook; the API can include a secret header with each delivery.[1]

| Credential | Used by | Store as |
|---|---|---|
| Telegram bot token | Web service | `TELEGRAM_BOT_TOKEN` |
| OpenAI API key | Web service | `OPENAI_API_KEY` |
| Administrator password hash | Web service | `ADMIN_PASSWORD_HASH` |
| Application signing secret | Web service | `SECRET_KEY` |
| Telegram webhook secret | Telegram and web service | `TELEGRAM_WEBHOOK_SECRET` |
| Payment provider token | Web service, optional | `TELEGRAM_PAYMENT_PROVIDER_TOKEN` |

Do not use real secrets in `.env.example`, command history shared with other users, tickets, screenshots, or source control.

## 2. Prepare the repository

```bash
git clone <your-repository-url> nexusai
cd nexusai
cp .env.example .env
```

Generate an administrator password hash interactively:

```bash
python scripts/hash_password.py
```

Generate two independent secrets:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the first random value to `SECRET_KEY` and the second to `TELEGRAM_WEBHOOK_SECRET`. The webhook secret must contain only letters, digits, underscores, and hyphens, and Telegram permits 1–256 characters.[1]

## 3. Configure `.env`

At minimum, replace the following values:

```dotenv
ENVIRONMENT=development
PUBLIC_BASE_URL=https://your-public-domain.example
TELEGRAM_BOT_TOKEN=<botfather-token>
TELEGRAM_WEBHOOK_SECRET=<generated-token>
OPENAI_API_KEY=<openai-key>
ADMIN_USERNAME=<private-admin-name>
ADMIN_PASSWORD_HASH=<argon2-output>
SECRET_KEY=<generated-signing-secret>
```

For Docker Compose, leave the hostnames in `.env` as local defaults because `docker-compose.yml` overrides `DATABASE_URL` and `REDIS_URL` for the containers. For host-based installation, point them to running local or managed services:

```dotenv
DATABASE_URL=postgresql+asyncpg://nexusai:strong-password@127.0.0.1:5432/nexusai
REDIS_URL=redis://127.0.0.1:6379/0
```

`PUBLIC_BASE_URL` should have no trailing slash. `TELEGRAM_WEBHOOK_PATH` should begin with `/` and defaults to `/webhooks/telegram`.

## 4A. Install with Docker Compose

Confirm Docker availability:

```bash
docker --version
docker compose version
```

Build and start the stack:

```bash
docker compose up --build -d
```

Observe initialization:

```bash
docker compose ps
docker compose logs -f web worker
```

The web process applies the latest Alembic migration before starting Uvicorn. When PostgreSQL and Redis are healthy, seed the curated tools and prompts:

```bash
docker compose exec web python scripts/seed.py
```

The seed is idempotent, so it can be run again after interrupted setup.

## 4B. Install directly on a host

Install Python 3.12, PostgreSQL, and Redis. Create the database and a least-privilege application user, then create an isolated environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Apply the schema and seed content:

```bash
alembic upgrade head
python scripts/seed.py
```

Start the web process:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
```

Start the worker in a second process with the same environment:

```bash
python -m app.workers.scheduler
```

Use a service manager or container orchestrator in production. Do not rely on interactive terminal sessions for process persistence.

## 5. Verify the installation

Check liveness and readiness:

```bash
curl -fsS http://127.0.0.1:8000/health/live
curl -fsS http://127.0.0.1:8000/health/ready
```

A healthy response resembles:

```json
{"status":"ready","database":"ok","redis":"ok"}
```

Then verify the following sequence:

| Check | Expected result |
|---|---|
| Open `/admin` | Browser requests HTTP Basic credentials and loads the dashboard after authentication |
| Send `/start` | Bot registers the Telegram account and displays the main menu |
| Open AI Tools | Seeded tools appear |
| Open Prompt Library | Seeded prompt categories appear |
| Enter AI Chat | A normal text message returns an OpenAI-backed answer |
| Open Referrals | A deep link containing the user’s referral code appears |
| Inspect worker logs | Scheduler starts and scheduled jobs complete or wait for their interval |

If the bot does not respond, inspect web logs for webhook registration. The configured public URL must reach the FastAPI service over HTTPS. Railway can supply a public domain for a deployed service.[2]

## 6. Validate the project

From the host environment:

```bash
ruff format --check app tests
ruff check app tests
mypy app --ignore-missing-imports --check-untyped-defs
pytest -q
python scripts/validate_deployment.py
```

To validate migration reversibility against disposable data:

```bash
alembic downgrade base
alembic upgrade head
```

Never run a full downgrade against a production database without a reviewed migration plan and verified backup.

## 7. Configure optional Telegram payments

Obtain a Telegram-compatible payment provider token through BotFather, then set:

```dotenv
TELEGRAM_PAYMENT_PROVIDER_TOKEN=<provider-token>
PREMIUM_MONTHLY_PRICE_CENTS=999
PREMIUM_CURRENCY=USD
```

Restart or redeploy the web service. The upgrade button appears only when the provider token is non-empty. Complete provider sandbox testing before accepting live payments.

## 8. Day-two commands

| Operation | Command |
|---|---|
| Follow application logs | `docker compose logs -f web worker` |
| Stop services | `docker compose down` |
| Stop and delete local data | `docker compose down -v` |
| Apply migrations | `docker compose exec web alembic upgrade head` |
| Rerun content seed | `docker compose exec web python scripts/seed.py` |
| Run tests in host environment | `pytest -q` |
| Validate deployment files | `python scripts/validate_deployment.py` |

`docker compose down -v` permanently removes the local PostgreSQL and Redis volumes. Do not run it when the data must be retained.

## References

[1]: https://core.telegram.org/bots/api#setwebhook "Telegram Bot API — setWebhook"
[2]: https://docs.railway.com/guides/fastapi "Railway Docs — Deploy a FastAPI App"
