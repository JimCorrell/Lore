dev:
	docker compose up -d
	.venv/bin/uvicorn app.main:app --reload
