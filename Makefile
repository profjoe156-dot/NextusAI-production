.PHONY: install dev lint test migrate migration seed up down logs

install:
	python -m pip install -e '.[dev]'

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

lint:
	ruff check app tests

format:
	ruff format app tests

test:
	pytest --cov=app --cov-report=term-missing

migrate:
	alembic upgrade head

migration:
	alembic revision --autogenerate -m "$(m)"

seed:
	python scripts/seed.py

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f web worker
