# QUAN Recovery - Development Makefile

.PHONY: help install dev dev-seed dev-reset api dashboard seed migrate test lint clean

# Default target
help:
	@echo "QUAN Recovery - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install       Install all dependencies"
	@echo "  make migrate       Run database migrations"
	@echo "  make seed          Seed database with 1,000 test accounts"
	@echo ""
	@echo "Development:"
	@echo "  make dev           Start API + Dashboard (no seeding)"
	@echo "  make dev-seed      Start and seed if empty"
	@echo "  make dev-reset     Reset database and start fresh"
	@echo "  make api           Start API server only"
	@echo "  make dashboard     Start dashboard only"
	@echo ""
	@echo "Testing:"
	@echo "  make test          Run all tests"
	@echo "  make lint          Run linters"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean         Remove generated files"

# Install dependencies
install:
	pip install -e ".[dev]"
	cd dashboard && npm install

# Database migrations
migrate:
	alembic upgrade head

# Seed database
seed:
	python scripts/seed_data.py --count 1000

# Reset and seed database
seed-reset:
	python scripts/seed_data.py --reset --count 1000

# Start development environment
dev:
	./scripts/dev.sh

dev-seed:
	./scripts/dev.sh --seed

dev-reset:
	./scripts/dev.sh --reset

# Start API server only
api:
	python -m uvicorn quan.main:app --host 0.0.0.0 --port 8000 --reload

# Start dashboard only
dashboard:
	cd dashboard && npm run dev

# Run tests
test:
	pytest tests/ -v

# Run linters
lint:
	ruff check quan/
	mypy quan/ --ignore-missing-imports

# Clean generated files
clean:
	rm -f quan.db
	rm -rf __pycache__ .pytest_cache .mypy_cache
	rm -rf quan/__pycache__ quan/**/__pycache__
	rm -rf dashboard/.next dashboard/node_modules/.cache

# Docker development
docker-dev:
	docker-compose -f docker-compose.dev.yaml up --build

docker-dev-down:
	docker-compose -f docker-compose.dev.yaml down
