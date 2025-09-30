# ========================================
# SamBot 2.0 - Makefile
# ========================================

.PHONY: help install up down logs clean migrate test

help: ## Show this help message
	@echo "SamBot 2.0 - Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	pip install -r requirements.txt

up: ## Start all services
	docker-compose up -d

up-db: ## Start only database and Redis
	docker-compose up -d postgres redis

down: ## Stop all services
	docker-compose down

logs: ## Show logs from all services
	docker-compose logs -f

logs-db: ## Show PostgreSQL logs
	docker-compose logs -f postgres

clean: ## Stop services and remove volumes (WARNING: deletes data)
	docker-compose down -v

migrate: ## Run migration from SQLite to PostgreSQL
	python scripts/migrate_from_sqlite.py

psql: ## Connect to PostgreSQL
	docker exec -it sambot_v2_postgres psql -U sambot -d sambot_v2

redis: ## Connect to Redis CLI
	docker exec -it sambot_v2_redis redis-cli

check-dmr: ## Check Docker Model Runner status
	@curl -s http://localhost:12434/health || echo "Docker Model Runner not available"

status: ## Show status of all services
	docker-compose ps

test: ## Run tests
	pytest tests/ -v

format: ## Format code with black
	black .

lint: ## Lint code with ruff
	ruff check .

backup: ## Create database backup
	docker exec sambot_v2_postgres pg_dump -U sambot sambot_v2 > backup_$(shell date +%Y%m%d_%H%M%S).sql

restore: ## Restore database from backup (usage: make restore FILE=backup.sql)
	docker exec -i sambot_v2_postgres psql -U sambot -d sambot_v2 < $(FILE)