.PHONY: dev stop restart migrate test

dev:
	docker compose up -d
	.venv/bin/uvicorn app.main:app --reload

stop:
	-pkill -f "uvicorn app.main:app" 2>/dev/null || true

restart: stop
	docker compose up -d
	.venv/bin/uvicorn app.main:app --reload

migrate:
	.venv/bin/alembic upgrade head

test:
	.venv/bin/pytest tests/ -v
