.PHONY: dev api frontend migrate seed

dev:
	./scripts/dev.sh

api:
	alembic upgrade head
	uvicorn quan.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd dashboard && npm run dev

migrate:
	alembic upgrade head

seed:
	python3 scripts/seed_data.py --reset
