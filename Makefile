# ============================================
# Panama Papers Neo4j Project - Makefile
# ============================================
# This Makefile provides commands for development, testing, and deployment
# Usage: make <target>
# Run 'make help' to see all available commands

# ============================================
# Variables
# ============================================
PYTHON := python3
PIP := pip3
VENV := .venv
VENV_BIN := $(VENV)/bin
IMAGE_NAME := panama-papers-api
IMAGE_TAG := latest
COMPOSE := docker-compose
APP_DIR := app
TEST_DIR := tests
DATA_DIR := data

# Colors for output
COLOR_RESET := \033[0m
COLOR_BOLD := \033[1m
COLOR_GREEN := \033[32m
COLOR_YELLOW := \033[33m
COLOR_BLUE := \033[34m

# ============================================
# PHONY Targets
# ============================================
.PHONY: help venv install install-dev run run-dev test test-unit test-integration \
	lint format format-check clean clean-all \
	docker-build docker-run docker-stop docker-restart docker-logs docker-clean \
	docker-shell docker-shell-neo4j docker-ps docker-pull \
	seed-db backup-db restore-db \
	env-check env-create docs docs-serve \
	pre-commit ci-test security-check

# ============================================
# Default Target
# ============================================
.DEFAULT_GOAL := help

help: ## Display this help message
	@echo "$(COLOR_BOLD)Panama Papers Neo4j Project - Available Commands$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_BLUE)Development:$(COLOR_RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(COLOR_GREEN)%-20s$(COLOR_RESET) %s\n", $$1, $$2}' | \
		grep -E "venv|install|run|test|lint|format|clean"
	@echo ""
	@echo "$(COLOR_BLUE)Docker:$(COLOR_RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(COLOR_GREEN)%-20s$(COLOR_RESET) %s\n", $$1, $$2}' | \
		grep -E "docker-"
	@echo ""
	@echo "$(COLOR_BLUE)Database:$(COLOR_RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(COLOR_GREEN)%-20s$(COLOR_RESET) %s\n", $$1, $$2}' | \
		grep -E "seed|backup|restore"
	@echo ""
	@echo "$(COLOR_BLUE)Utilities:$(COLOR_RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(COLOR_GREEN)%-20s$(COLOR_RESET) %s\n", $$1, $$2}' | \
		grep -E "env-|docs|pre-commit|security"
	@echo ""

# ============================================
# Environment Setup
# ============================================
venv: ## Create Python virtual environment
	@echo "$(COLOR_BLUE)Creating virtual environment...$(COLOR_RESET)"
	$(PYTHON) -m venv $(VENV)
	@echo "$(COLOR_GREEN)Virtual environment created at $(VENV)$(COLOR_RESET)"
	@echo "$(COLOR_YELLOW)Activate with: source $(VENV_BIN)/activate$(COLOR_RESET)"

install: ## Install production dependencies
	@echo "$(COLOR_BLUE)Installing dependencies...$(COLOR_RESET)"
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "$(COLOR_GREEN)Dependencies installed successfully$(COLOR_RESET)"

install-dev: install ## Install development dependencies
	@echo "$(COLOR_BLUE)Installing development dependencies...$(COLOR_RESET)"
	$(PIP) install pytest pytest-asyncio pytest-cov
	$(PIP) install black isort pylint mypy flake8
	$(PIP) install httpx  # For testing FastAPI
	@echo "$(COLOR_GREEN)Development dependencies installed$(COLOR_RESET)"

env-check: ## Check if .env file exists
	@if [ ! -f .env ]; then \
		echo "$(COLOR_YELLOW)Warning: .env file not found$(COLOR_RESET)"; \
		echo "$(COLOR_YELLOW)Run 'make env-create' to create from template$(COLOR_RESET)"; \
		exit 1; \
	fi
	@echo "$(COLOR_GREEN).env file found$(COLOR_RESET)"

env-create: ## Create .env from .env.example
	@if [ -f .env ]; then \
		echo "$(COLOR_YELLOW).env already exists. Skipping...$(COLOR_RESET)"; \
	else \
		cp .env.example .env; \
		echo "$(COLOR_GREEN).env created from .env.example$(COLOR_RESET)"; \
		echo "$(COLOR_YELLOW)Please edit .env and update the values$(COLOR_RESET)"; \
	fi

# ============================================
# Running the Application
# ============================================
run: env-check ## Run FastAPI server locally (production mode)
	@echo "$(COLOR_BLUE)Starting FastAPI server...$(COLOR_RESET)"
	uvicorn $(APP_DIR).main:app --host 0.0.0.0 --port 8000

run-dev: env-check ## Run FastAPI server with auto-reload (development mode)
	@echo "$(COLOR_BLUE)Starting FastAPI server in development mode...$(COLOR_RESET)"
	uvicorn $(APP_DIR).main:app --host 0.0.0.0 --port 8000 --reload

# ============================================
# Testing
# ============================================
test: ## Run all tests with coverage
	@echo "$(COLOR_BLUE)Running tests with coverage...$(COLOR_RESET)"
	pytest $(TEST_DIR)/ -v --cov=$(APP_DIR) --cov-report=html --cov-report=term-missing
	@echo "$(COLOR_GREEN)Tests completed. Coverage report: htmlcov/index.html$(COLOR_RESET)"

test-unit: ## Run unit tests only
	@echo "$(COLOR_BLUE)Running unit tests...$(COLOR_RESET)"
	pytest $(TEST_DIR)/unit/ -v

test-integration: ## Run integration tests only
	@echo "$(COLOR_BLUE)Running integration tests...$(COLOR_RESET)"
	pytest $(TEST_DIR)/integration/ -v

test-watch: ## Run tests in watch mode
	@echo "$(COLOR_BLUE)Running tests in watch mode...$(COLOR_RESET)"
	pytest-watch $(TEST_DIR)/ -v

ci-test: ## Run tests for CI/CD (no coverage report)
	@echo "$(COLOR_BLUE)Running CI tests...$(COLOR_RESET)"
	pytest $(TEST_DIR)/ -v --maxfail=1 --tb=short

# ============================================
# Code Quality
# ============================================
lint: ## Run pylint on app directory
	@echo "$(COLOR_BLUE)Running pylint...$(COLOR_RESET)"
	pylint $(APP_DIR)/ --rcfile=.pylintrc || true

format: ## Format code with black and isort
	@echo "$(COLOR_BLUE)Formatting code with black...$(COLOR_RESET)"
	black $(APP_DIR)/ $(TEST_DIR)/
	@echo "$(COLOR_BLUE)Sorting imports with isort...$(COLOR_RESET)"
	isort $(APP_DIR)/ $(TEST_DIR)/
	@echo "$(COLOR_GREEN)Code formatted successfully$(COLOR_RESET)"

format-check: ## Check code formatting without modifying
	@echo "$(COLOR_BLUE)Checking code format...$(COLOR_RESET)"
	black --check $(APP_DIR)/ $(TEST_DIR)/
	isort --check-only $(APP_DIR)/ $(TEST_DIR)/

type-check: ## Run mypy type checking
	@echo "$(COLOR_BLUE)Running type checks...$(COLOR_RESET)"
	mypy $(APP_DIR)/

security-check: ## Run security checks with bandit
	@echo "$(COLOR_BLUE)Running security checks...$(COLOR_RESET)"
	pip install bandit safety
	bandit -r $(APP_DIR)/
	safety check

pre-commit: format lint test ## Run all pre-commit checks
	@echo "$(COLOR_GREEN)All pre-commit checks passed!$(COLOR_RESET)"

# ============================================
# Docker Commands
# ============================================
docker-build: ## Build Docker images
	@echo "$(COLOR_BLUE)Building Docker images...$(COLOR_RESET)"
	$(COMPOSE) build
	@echo "$(COLOR_GREEN)Docker images built successfully$(COLOR_RESET)"

docker-run: env-check ## Start all services with docker-compose
	@echo "$(COLOR_BLUE)Starting Docker services...$(COLOR_RESET)"
	$(COMPOSE) up -d
	@echo "$(COLOR_GREEN)Services started successfully$(COLOR_RESET)"
	@echo "$(COLOR_YELLOW)API: http://localhost:8000$(COLOR_RESET)"
	@echo "$(COLOR_YELLOW)Docs: http://localhost:8000/docs$(COLOR_RESET)"
	@echo "$(COLOR_YELLOW)Neo4j Browser: http://localhost:7474$(COLOR_RESET)"

docker-stop: ## Stop all Docker services
	@echo "$(COLOR_BLUE)Stopping Docker services...$(COLOR_RESET)"
	$(COMPOSE) down
	@echo "$(COLOR_GREEN)Services stopped$(COLOR_RESET)"

docker-restart: ## Restart all Docker services
	@echo "$(COLOR_BLUE)Restarting Docker services...$(COLOR_RESET)"
	$(COMPOSE) restart
	@echo "$(COLOR_GREEN)Services restarted$(COLOR_RESET)"

docker-logs: ## View logs from all services (follow mode)
	@echo "$(COLOR_BLUE)Showing Docker logs (Ctrl+C to exit)...$(COLOR_RESET)"
	$(COMPOSE) logs -f

docker-logs-api: ## View FastAPI logs only
	@echo "$(COLOR_BLUE)Showing FastAPI logs (Ctrl+C to exit)...$(COLOR_RESET)"
	$(COMPOSE) logs -f fastapi

docker-logs-neo4j: ## View Neo4j logs only
	@echo "$(COLOR_BLUE)Showing Neo4j logs (Ctrl+C to exit)...$(COLOR_RESET)"
	$(COMPOSE) logs -f neo4j

docker-ps: ## Show status of all Docker services
	@echo "$(COLOR_BLUE)Docker services status:$(COLOR_RESET)"
	$(COMPOSE) ps

docker-shell: ## Open shell in FastAPI container
	@echo "$(COLOR_BLUE)Opening shell in FastAPI container...$(COLOR_RESET)"
	$(COMPOSE) exec fastapi bash

docker-shell-neo4j: ## Open Neo4j Cypher shell
	@echo "$(COLOR_BLUE)Opening Neo4j Cypher shell...$(COLOR_RESET)"
	$(COMPOSE) exec neo4j cypher-shell -u neo4j -p $${NEO4J_PASSWORD:-testpassword123}

docker-clean: ## Remove all containers, volumes, and networks
	@echo "$(COLOR_YELLOW)Warning: This will remove all data!$(COLOR_RESET)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "$(COLOR_BLUE)Cleaning up Docker resources...$(COLOR_RESET)"; \
		$(COMPOSE) down -v --remove-orphans; \
		echo "$(COLOR_GREEN)Docker resources cleaned$(COLOR_RESET)"; \
	fi

docker-pull: ## Pull latest Docker images
	@echo "$(COLOR_BLUE)Pulling latest images...$(COLOR_RESET)"
	$(COMPOSE) pull
	@echo "$(COLOR_GREEN)Images updated$(COLOR_RESET)"

docker-rebuild: docker-stop docker-build docker-run ## Rebuild and restart all services

# ============================================
# Database Management
# ============================================
seed-db: env-check ## Run database seeding script
	@echo "$(COLOR_BLUE)Seeding database...$(COLOR_RESET)"
	$(PYTHON) scripts/seed_database.py
	@echo "$(COLOR_GREEN)Database seeded successfully$(COLOR_RESET)"

backup-db: ## Backup Neo4j database
	@echo "$(COLOR_BLUE)Creating database backup...$(COLOR_RESET)"
	@mkdir -p backups
	$(COMPOSE) exec neo4j neo4j-admin dump --database=neo4j --to=/backups/neo4j-backup-$$(date +%Y%m%d-%H%M%S).dump
	@echo "$(COLOR_GREEN)Backup created in backups/ directory$(COLOR_RESET)"

restore-db: ## Restore Neo4j database from backup
	@echo "$(COLOR_YELLOW)Available backups:$(COLOR_RESET)"
	@ls -lh backups/*.dump 2>/dev/null || echo "No backups found"
	@read -p "Enter backup filename: " backup_file; \
	if [ -f "backups/$$backup_file" ]; then \
		echo "$(COLOR_BLUE)Restoring from $$backup_file...$(COLOR_RESET)"; \
		$(COMPOSE) exec neo4j neo4j-admin load --from=/backups/$$backup_file --database=neo4j --force; \
		echo "$(COLOR_GREEN)Database restored$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_YELLOW)Backup file not found$(COLOR_RESET)"; \
	fi

db-reset: docker-clean docker-run seed-db ## Reset database (clean, restart, seed)
	@echo "$(COLOR_GREEN)Database reset complete$(COLOR_RESET)"

# ============================================
# Cleanup
# ============================================
clean: ## Clean Python cache and test artifacts
	@echo "$(COLOR_BLUE)Cleaning Python cache files...$(COLOR_RESET)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache .ruff_cache
	rm -rf build dist
	@echo "$(COLOR_GREEN)Cleanup complete$(COLOR_RESET)"

clean-all: clean docker-clean ## Clean everything including Docker resources
	@echo "$(COLOR_BLUE)Removing virtual environment...$(COLOR_RESET)"
	rm -rf $(VENV)
	@echo "$(COLOR_GREEN)Full cleanup complete$(COLOR_RESET)"

# ============================================
# Documentation
# ============================================
docs: ## Generate API documentation
	@echo "$(COLOR_BLUE)Generating documentation...$(COLOR_RESET)"
	@mkdir -p docs
	$(PYTHON) scripts/generate_docs.py
	@echo "$(COLOR_GREEN)Documentation generated in docs/$(COLOR_RESET)"

docs-serve: ## Serve documentation locally
	@echo "$(COLOR_BLUE)Starting documentation server...$(COLOR_RESET)"
	@echo "$(COLOR_YELLOW)Documentation available at http://localhost:8001$(COLOR_RESET)"
	cd docs && $(PYTHON) -m http.server 8001

# ============================================
# Utilities
# ============================================
check-deps: ## Check for outdated dependencies
	@echo "$(COLOR_BLUE)Checking for outdated dependencies...$(COLOR_RESET)"
	$(PIP) list --outdated

update-deps: ## Update dependencies to latest versions
	@echo "$(COLOR_BLUE)Updating dependencies...$(COLOR_RESET)"
	$(PIP) install --upgrade -r requirements.txt
	@echo "$(COLOR_GREEN)Dependencies updated$(COLOR_RESET)"

freeze-deps: ## Freeze current dependencies to requirements.txt
	@echo "$(COLOR_BLUE)Freezing dependencies...$(COLOR_RESET)"
	$(PIP) freeze > requirements.txt
	@echo "$(COLOR_GREEN)Dependencies frozen to requirements.txt$(COLOR_RESET)"

health-check: ## Check health of all services
	@echo "$(COLOR_BLUE)Checking service health...$(COLOR_RESET)"
	@echo "$(COLOR_YELLOW)API Health:$(COLOR_RESET)"
	@curl -f http://localhost:8000/health 2>/dev/null && echo " ✓" || echo " ✗"
	@echo "$(COLOR_YELLOW)Neo4j Health:$(COLOR_RESET)"
	@curl -f http://localhost:7474 2>/dev/null && echo " ✓" || echo " ✗"

setup: venv install-dev env-create docker-build ## Complete project setup (first time)
	@echo "$(COLOR_GREEN)Project setup complete!$(COLOR_RESET)"
	@echo "$(COLOR_YELLOW)Next steps:$(COLOR_RESET)"
	@echo "  1. Activate virtual environment: source $(VENV_BIN)/activate"
	@echo "  2. Edit .env with your configuration"
	@echo "  3. Start services: make docker-run"
	@echo "  4. Visit: http://localhost:8000/docs"

status: ## Show project status
	@echo "$(COLOR_BOLD)Panama Papers Neo4j Project Status$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_BLUE)Environment:$(COLOR_RESET)"
	@if [ -d $(VENV) ]; then \
		echo "  Virtual environment: $(COLOR_GREEN)✓ Created$(COLOR_RESET)"; \
	else \
		echo "  Virtual environment: $(COLOR_YELLOW)✗ Not created$(COLOR_RESET)"; \
	fi
	@if [ -f .env ]; then \
		echo "  .env file: $(COLOR_GREEN)✓ Present$(COLOR_RESET)"; \
	else \
		echo "  .env file: $(COLOR_YELLOW)✗ Missing$(COLOR_RESET)"; \
	fi
	@echo ""
	@echo "$(COLOR_BLUE)Docker Services:$(COLOR_RESET)"
	@$(COMPOSE) ps 2>/dev/null || echo "  $(COLOR_YELLOW)Services not running$(COLOR_RESET)"