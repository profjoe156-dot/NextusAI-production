# NexusAI Production Operations

This guide defines the minimum operational practices for running NexusAI after deployment. Adapt alert thresholds and recovery objectives to the business, data classification, traffic, and provider limits.

## Service objectives and ownership

Assign a named owner for the web service, worker, PostgreSQL, Redis, Telegram bot credential, OpenAI account, payment provider, and Railway project. Record how to contact that owner during an incident and who is authorized to rotate credentials or grant premium access.

| Component | Critical user impact when unavailable | Primary signal |
|---|---|---|
| Web service | Telegram updates, admin dashboard, and health endpoints stop | `/health/live`, HTTP errors, webhook failures |
| PostgreSQL | Registration, chat persistence, content, referrals, and membership fail | `/health/ready`, connection errors, pool saturation |
| Redis | Readiness fails; rate limiting and job coordination stop | `/health/ready`, Redis latency/errors |
| OpenAI | AI chat fails while directory and account functions may continue | Provider error rate, latency, cost limits |
| Worker | News becomes stale and premium expiry processing is delayed | Worker heartbeat/log silence, job completion logs |
| Telegram | Updates or outgoing messages are unavailable | Telegram API errors and webhook delivery state |

## Launch checklist

Before directing users to the bot, confirm all placeholders are replaced, production secrets are unique, HTTPS is active, PostgreSQL backups are enabled, and the admin username is not the example default. Run migrations and the content seed, verify the worker, exercise a free and premium account, and test a referral with two non-production Telegram accounts.

| Control | Required evidence |
|---|---|
| Readiness | `/health/ready` returns HTTP 200 with database and Redis `ok` |
| Migrations | `alembic current` reports the expected head revision |
| Webhook | Startup log reports `telegram_webhook_configured` for the production URL |
| AI | Test prompt returns a response and records token/usage data |
| Admin | Dashboard loads; block/unblock and premium grant work on a test user |
| Worker | News refresh and premium-expiry job logs appear |
| Payment, if enabled | Provider sandbox purchase completes and activates exactly once |
| Recovery | A recent PostgreSQL backup can be restored in a non-production environment |

## Monitoring and alerts

Scrape or inspect `/metrics` behind an authenticated or private boundary. Monitor request count, latency, and failure ratio together with platform CPU, memory, restarts, network, database connections, storage, and Redis memory.

Recommended initial alerts are starting points rather than universal thresholds:

| Alert | Initial condition | Operator action |
|---|---|---|
| Web unavailable | Two consecutive readiness failures over two minutes | Inspect web, PostgreSQL, and Redis status and recent deployment logs |
| Elevated server errors | HTTP 5xx exceeds 2% for five minutes | Correlate request IDs and isolate dependency or release failures |
| Slow API | p95 request latency exceeds two seconds for ten minutes | Separate provider latency from database, Redis, and application latency |
| Repeated restarts | More than three web or worker restarts in ten minutes | Inspect out-of-memory, failed settings, migration, and connection errors |
| Database saturation | Connections exceed 80% of provider limit | Reduce replica pool totals or increase database capacity |
| OpenAI cost anomaly | Daily spend or tokens exceed the expected envelope | Check abuse, quotas, model choice, and compromised credentials |
| Worker silence | No successful job event over two expected intervals | Verify worker state, scheduler setting, Redis locks, and feed availability |
| News staleness | Newest article exceeds the business freshness target | Trigger manual refresh and inspect feeds and worker logs |

## Logs and request correlation

The FastAPI middleware accepts or generates `X-Request-ID` and returns it in the response. Record this value in incident notes and use it to correlate API errors. Worker logs identify job names and completion/failure events.

Do not add logging of Telegram bot tokens, OpenAI keys, payment tokens, Basic credentials, signing secrets, raw cookies, or complete payment payloads. Treat user prompts and AI responses as potentially sensitive; log only what the approved retention policy permits.

## Routine maintenance

| Frequency | Activity |
|---|---|
| Daily | Review service health, error rate, OpenAI usage, provider incidents, and failed jobs |
| Weekly | Review blocked users, abnormal quota usage, news freshness, dependency advisories, and database growth |
| Monthly | Test a backup restore, review access, rotate expiring credentials, inspect slow queries, and verify payment reconciliation |
| Before every release | Run tests, lint, type checks, migration validation, image build, and a staging smoke test |
| After every release | Verify readiness, webhook registration, AI chat, worker logs, admin dashboard, and key user flows |

Apply dependency updates through reviewed pull requests. Test migrations against a copy or representative disposable database. Avoid making unreviewed schema changes directly in production.

## Backup and restore

PostgreSQL is the durable system of record. Configure managed backups with retention that meets the business recovery-point objective. Redis contains coordination and rate-limit state; persistent Redis data is useful but should not be treated as the only copy of durable business records.

A restore drill should create an isolated database, restore the selected backup, run integrity queries, point a non-production NexusAI deployment at it, and exercise registration, account, prompt, referral, and premium reads. Record backup timestamp, restore duration, migration revision, row counts, and any manual remediation.

Before restoring production, determine whether the incident requires a full restore, point-in-time recovery, or a targeted data correction. Stop or isolate writers where necessary to avoid overwriting recovered state.

## Incident runbooks

### Bot is online but does not answer

Check `/health/ready`, web deployment logs, and Telegram API errors. Confirm `PUBLIC_BASE_URL` and `TELEGRAM_WEBHOOK_PATH` form the correct HTTPS endpoint and that the web startup registered it. Confirm the webhook secret uses only permitted characters and matches the web environment. If a token was rotated, update all services and redeploy.

### AI chat fails while menus work

Inspect provider status, OpenAI authentication errors, model access, timeout logs, and account budget. Confirm only AI requests fail. If costs or abuse are suspected, reduce quotas or disable affected users while preserving directory, prompt, and account access.

### Readiness fails on PostgreSQL

Check the managed database state, private networking, credentials, pool exhaustion, and migration status. Compare configured aggregate pool capacity with the provider connection limit. Avoid repeatedly restarting every replica when the root cause is database saturation.

### Readiness fails on Redis

Check Redis availability, credentials, private networking, memory pressure, and eviction behavior. Web readiness intentionally fails because rate limiting and coordination are required production dependencies. Restore the shared Redis reference before scaling services.

### Worker is not refreshing news

Confirm the worker is running with `SCHEDULER_ENABLED=true`. Inspect feed URL parsing, outbound networking, and job errors. Verify every worker shares Redis; stale locks naturally expire after their TTL. Trigger `/api/admin/news/refresh` with administrator authentication and `X-Admin-Action: NexusAI` to distinguish scheduler failure from ingestion failure.

### Payment completed but premium is absent

Record the Telegram user ID and payment charge reference without exposing provider secrets. Check successful-payment logs and the payment/subscription rows. Do not issue a second charge. If granting access manually, use the admin endpoint and document the corrective grant for reconciliation.

### Administrator credential compromise

Change the source password, generate a new Argon2 hash, update `ADMIN_PASSWORD_HASH`, rotate `SECRET_KEY` if sessions may be exposed, redeploy, and review administrative actions. Restrict dashboard access at the platform edge if not already restricted.

### Telegram token compromise

Revoke and regenerate the token through BotFather, update the web and worker variables, redeploy, and verify webhook registration. Review outgoing messages and platform activity during the exposure window.

## Scaling

Web replicas are stateless with respect to durable data, but each creates database pool capacity. Keep total possible connections below the provider limit with operating reserve. Redis coordinates per-user request limits across replicas.

The scheduler can run more than one replica for availability because jobs acquire Redis ownership locks. A lock is not a substitute for idempotent writes; news inserts and membership transitions are designed to tolerate retries. Maintain the worker as a separate Railway service so web scaling does not multiply scheduled execution.

Scale only after identifying the constrained resource. Increasing web replicas will not resolve a saturated database, OpenAI provider throttling, or an undersized connection limit.

## Deployment and rollback

Every release should pass the repository CI checks and a staging smoke test. Use `alembic upgrade head` as a controlled pre-deploy operation. Prefer backward-compatible migrations so an earlier application image can run during rollback.

If a new release fails but the schema is compatible, roll back the application image first. If the migration itself is defective, stop writers, take a fresh backup, and follow the reviewed recovery plan. Never assume application rollback reverses the database.

## Data and privacy

Define retention for user profiles, Telegram identifiers, prompts, AI responses, message metadata, referrals, and payment references. Provide an approved process for access and deletion requests applicable to the operating jurisdiction. Restrict production database access and audit administrative access using Railway and database controls.

Before adding analytics, external logging, or support tooling, verify where user content will be sent and whether the data-processing terms are acceptable. Minimize content copied into incidents and tickets.
