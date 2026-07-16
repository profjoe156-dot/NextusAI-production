# Deploy NexusAI to Railway

This runbook deploys NexusAI as four Railway services in one project: managed PostgreSQL, managed Redis, a public FastAPI **web** service, and a private **worker** service. Railway supports Dockerfile-based FastAPI deployment and provides a public domain through service networking.[1]

## Target topology

| Railway service | Source | Public domain | Start command |
|---|---|---:|---|
| PostgreSQL | Railway database | No | Managed |
| Redis | Railway database | No | Managed |
| `nexusai-web` | Git repository | Yes | Defined in `railway.toml` |
| `nexusai-worker` | Same Git repository | No | `python -m app.workers.scheduler` |

Both application services must reference the same PostgreSQL and Redis instances. The web service registers the Telegram webhook; the worker handles scheduled work.

## 1. Prepare the repository

Push the completed NexusAI repository to a Git provider supported by Railway. Before deployment, run:

```bash
ruff check app tests
mypy app --ignore-missing-imports --check-untyped-defs
pytest -q
python scripts/validate_deployment.py
docker build -t nexusai:release .
```

Do not commit `.env`. Railway variables replace it in production.

## 2. Create the Railway project and databases

Create a new Railway project. Add a PostgreSQL service and a Redis service using Railway’s managed database templates. Keep both private unless an external administrative connection is explicitly required.

Record or reference the provided database connection values. NexusAI expects an async SQLAlchemy URL, so the web and worker values must use the `postgresql+asyncpg` scheme:

```text
postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>
```

Redis should use the provider URL directly:

```text
redis://<host>:<port>/<database-number>
```

Prefer Railway variable references to copied credentials so rotations and service changes propagate safely.

## 3. Create the web service

Create a service from the Git repository and name it `nexusai-web`. The root [`railway.toml`](../railway.toml) configures:

| Setting | Value |
|---|---|
| Builder | Repository `Dockerfile` |
| Start | Uvicorn on Railway’s `$PORT` |
| Pre-deploy | `alembic upgrade head` |
| Health check | `/health/ready` |
| Restart | On failure, up to ten retries |

Generate a public domain from the service’s networking settings. Railway’s FastAPI guidance describes Dockerfile deployment and public domain generation.[1]

## 4. Create the worker service

Create a second service from the same repository and name it `nexusai-worker`. Configure it to use [`railway.worker.toml`](../railway.worker.toml). If the dashboard does not automatically select that file for the service, copy its values into the service settings:

```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "python -m app.workers.scheduler"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

The worker does not need a public domain and must not run the Uvicorn command.

## 5. Configure shared variables

Set these variables on both application services unless the table says otherwise. Use a Railway shared variable group when available.

| Variable | Web | Worker | Guidance |
|---|---:|---:|---|
| `ENVIRONMENT=production` | Yes | Yes | Enables production behavior |
| `PUBLIC_BASE_URL` | Yes | Yes | `https://<web-domain>`, no trailing slash |
| `DATABASE_URL` | Yes | Yes | Reference managed PostgreSQL; use `postgresql+asyncpg` |
| `REDIS_URL` | Yes | Yes | Reference managed Redis |
| `TELEGRAM_BOT_TOKEN` | Yes | Yes | BotFather token; worker settings validation also requires it |
| `TELEGRAM_WEBHOOK_SECRET` | Yes | Yes | Random letters/digits/underscore/hyphen token |
| `OPENAI_API_KEY` | Yes | Yes | Web uses it; shared config keeps deployments uniform |
| `ADMIN_USERNAME` | Yes | Yes | Private, non-default value |
| `ADMIN_PASSWORD_HASH` | Yes | Yes | Argon2 output, not plaintext |
| `SECRET_KEY` | Yes | Yes | At least 64 random URL-safe characters |
| `NEWS_FEED_URLS` | Yes | Yes | Comma-separated feed URLs |
| `SCHEDULER_ENABLED` | No | Yes | Set `true` on worker; it is not used by web |
| `TELEGRAM_PAYMENT_PROVIDER_TOKEN` | Optional | Optional | Empty disables checkout |

Copy the remaining quota, pool, model, timeout, pricing, and scheduling defaults from [`.env.example`](../.env.example), adjusting them for expected traffic and provider budgets.

Generate production secrets locally:

```bash
python scripts/hash_password.py
python -c "import secrets; print(secrets.token_urlsafe(64))"
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Telegram permits a webhook `secret_token` of 1–256 characters containing letters, digits, underscores, and hyphens; Telegram returns it in `X-Telegram-Bot-Api-Secret-Token`.[2]

## 6. First deployment order

Deploy in this order:

1. Wait for PostgreSQL and Redis to become available.
2. Deploy `nexusai-web`; its pre-deploy command applies the schema.
3. Seed content once by opening a Railway shell for the web service and running `python scripts/seed.py`.
4. Deploy `nexusai-worker`.
5. Redeploy the web service after `PUBLIC_BASE_URL` is set to the final public domain.

The web lifecycle calls Telegram `setWebhook` during startup. A successful startup log includes `telegram_webhook_configured` with the configured URL.

## 7. Verify the release

From a trusted terminal, run:

```bash
curl -fsS https://<web-domain>/health/live
curl -fsS https://<web-domain>/health/ready
```

Expected readiness fields are `status`, `database`, and `redis`. Then check:

| Verification | Expected result |
|---|---|
| Web deployment logs | Migration completes and Uvicorn starts |
| Worker deployment logs | Scheduler starts without connection errors |
| `/admin` | Basic-auth prompt appears and dashboard loads |
| Telegram `/start` | User registers and the main menu appears |
| AI Chat | OpenAI response is returned and usage increases |
| AI Tools/Prompts | Seeded content appears |
| Referral deep link | Second account registration attributes and rewards once |
| Manual news refresh | Admin action returns a successful refresh result |

If Telegram messages do not arrive, compare the registered webhook URL with `PUBLIC_BASE_URL + TELEGRAM_WEBHOOK_PATH`, verify the secret uses allowed characters, and inspect startup errors. Do not disable webhook authentication as a troubleshooting shortcut.

## 8. Scale safely

Web replicas can be increased after validating database pool capacity. Total potential PostgreSQL connections are approximately:

```text
web replicas × (DB_POOL_SIZE + DB_MAX_OVERFLOW) + worker connections + administrative reserve
```

Set per-replica pools so the total remains under the managed database limit. All replicas must share PostgreSQL and Redis. Redis-backed rate limits coordinate users across web replicas, while worker locks prevent simultaneous duplicate jobs.

Avoid deploying a large number of web replicas without considering Telegram’s configured webhook connection count. `TELEGRAM_MAX_CONNECTIONS` controls the maximum simultaneous webhook connections requested during registration; Telegram documents a range of 1–100 and a default of 40.[2]

## 9. Rollback and migration safety

Railway can restart an earlier application image, but an application rollback does not automatically reverse a database migration. Before schema-changing releases:

1. Review the Alembic revision.
2. Take and verify a database backup.
3. Prefer backward-compatible schema additions.
4. Deploy code that tolerates both old and new schema during transitions.
5. Run data backfills separately for large tables.
6. Remove old columns only after every active version no longer reads them.

Use `alembic downgrade` in production only when the downgrade has been tested against representative data and the migration is known to be reversible.

## 10. Production controls

Protect the admin dashboard with strong Basic credentials and, where available, an IP allowlist, identity-aware proxy, or private access layer. Keep metrics private or protect `/metrics` at the edge. Configure Railway log retention or external log shipping, uptime checks for `/health/ready`, PostgreSQL backups, Redis persistence appropriate to its coordination role, OpenAI budget alerts, and payment-provider alerts.

Rotate a compromised Telegram token through BotFather, update both services, and redeploy. Rotate webhook and signing secrets independently. Database and Redis credential rotation should update the shared references before old credentials are revoked.

## References

[1]: https://docs.railway.com/guides/fastapi "Railway Docs — Deploy a FastAPI App"
[2]: https://core.telegram.org/bots/api#setwebhook "Telegram Bot API — setWebhook"
