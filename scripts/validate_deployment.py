from pathlib import Path
import tomllib

import yaml

ROOT = Path(__file__).resolve().parents[1]

for name in ("railway.toml", "railway.worker.toml"):
    with (ROOT / name).open("rb") as handle:
        config = tomllib.load(handle)
    assert config["build"]["builder"] == "DOCKERFILE"
    assert config["deploy"]["startCommand"]

compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
assert {"postgres", "redis", "web", "worker"}.issubset(compose["services"])
assert compose["services"]["web"]["depends_on"]["postgres"]["condition"] == "service_healthy"
assert compose["services"]["worker"]["command"] == "python -m app.workers.scheduler"

dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
for required in ("FROM python:3.12-slim", "USER nexusai", "HEALTHCHECK", "uvicorn app.main:app"):
    assert required in dockerfile, required

env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
for required in (
    "DATABASE_URL=",
    "REDIS_URL=",
    "TELEGRAM_BOT_TOKEN=",
    "TELEGRAM_WEBHOOK_SECRET=",
    "OPENAI_API_KEY=",
    "ADMIN_PASSWORD_HASH=",
    "SECRET_KEY=",
):
    assert required in env_example, required

print("Deployment configuration validation passed.")
