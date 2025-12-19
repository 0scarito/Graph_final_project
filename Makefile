# ============================================
# Panama Papers Neo4j Project - Makefile
# ============================================
# Windows & Linux Compatible
# Usage: make <target>

# Variables
PYTHON := python
PIP := pip
COMPOSE := docker-compose
APP_DIR := app
TEST_DIR := tests

.PHONY: help install install-dev run run-dev test lint format clean \
	docker-build docker-run docker-stop docker-restart docker-logs docker-ps docker-clean \
	seed-db health-check

.DEFAULT_GOAL := help

help: ## Display this help message
	@echo.
	@echo Panama Papers Neo4j Project - Available Commands
	@echo.
	@echo Development:
	@echo   install        Install production dependencies
	@echo   install-dev    Install development dependencies
	@echo   run            Run FastAPI server locally
	@echo   run-dev        Run FastAPI with auto-reload
	@echo   test           Run all tests with coverage
	@echo   lint           Run pylint
	@echo   format         Format code with black
	@echo   clean          Clean cache files
	@echo.
	@echo Docker:
	@echo   docker-build   Build Docker images
	@echo   docker-run     Start all services
	@echo   docker-stop    Stop all services
	@echo   docker-restart Restart services
	@echo   docker-logs    View logs (follow mode)
	@echo   docker-ps      Show service status
	@echo   docker-clean   Remove containers and volumes
	@echo.
	@echo Database:
	@echo   seed-db        Run database seeding script
	@echo   health-check   Check service health
	@echo.

# ============================================
# Development
# ============================================
install: ## Install production dependencies
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install-dev: install ## Install development dependencies
	$(PIP) install pytest pytest-asyncio pytest-cov
	$(PIP) install black isort pylint mypy flake8
	$(PIP) install httpx

run: ## Run FastAPI server locally
	uvicorn $(APP_DIR).main:app --host 0.0.0.0 --port 8000

run-dev: ## Run FastAPI server with auto-reload
	uvicorn $(APP_DIR).main:app --host 0.0.0.0 --port 8000 --reload

# ============================================
# Testing
# ============================================
test: ## Run all tests with coverage
	pytest $(TEST_DIR)/ -v --cov=$(APP_DIR) --cov-report=html --cov-report=term-missing

test-unit: ## Run unit tests only
	pytest $(TEST_DIR)/unit/ -v

test-integration: ## Run integration tests only
	pytest $(TEST_DIR)/integration/ -v

# ============================================
# Code Quality
# ============================================
lint: ## Run pylint on app directory
	pylint $(APP_DIR)/ --rcfile=.pylintrc

format: ## Format code with black and isort
	black $(APP_DIR)/ $(TEST_DIR)/
	isort $(APP_DIR)/ $(TEST_DIR)/

format-check: ## Check code formatting without modifying
	black --check $(APP_DIR)/ $(TEST_DIR)/
	isort --check-only $(APP_DIR)/ $(TEST_DIR)/

# ============================================
# Docker Commands
# ============================================
docker-build: ## Build Docker images
	$(COMPOSE) build

docker-run: ## Start all services with docker-compose
	$(COMPOSE) up -d
	@echo.
	@echo Services started successfully!
	@echo   API:          http://localhost:8000
	@echo   Swagger Docs: http://localhost:8000/docs
	@echo   Neo4j Browser: http://localhost:7474
	@echo.

docker-stop: ## Stop all Docker services
	$(COMPOSE) down

docker-restart: ## Restart all Docker services
	$(COMPOSE) restart

docker-logs: ## View logs from all services (follow mode)
	$(COMPOSE) logs -f

docker-logs-api: ## View FastAPI logs only
	$(COMPOSE) logs -f fastapi

docker-logs-neo4j: ## View Neo4j logs only
	$(COMPOSE) logs -f neo4j

docker-ps: ## Show status of all Docker services
	$(COMPOSE) ps

docker-shell: ## Open shell in FastAPI container
	$(COMPOSE) exec fastapi bash

docker-shell-neo4j: ## Open Neo4j Cypher shell
	$(COMPOSE) exec neo4j cypher-shell -u neo4j -p changeme123

docker-clean: ## Remove all containers, volumes, and networks
	$(COMPOSE) down -v --remove-orphans

docker-rebuild: docker-stop docker-build docker-run ## Rebuild and restart all services

# ============================================
# Database Management
# ============================================
seed-db: ## Run database seeding script
	$(PYTHON) scripts/seeddata.py

# ============================================
# Cleanup
# ============================================
clean: ## Clean Python cache files
	-rmdir /s /q __pycache__ 2>nul
	-rmdir /s /q .pytest_cache 2>nul
	-rmdir /s /q htmlcov 2>nul
	-rmdir /s /q .mypy_cache 2>nul
	-del /q .coverage 2>nul

# ============================================
# Utilities
# ============================================
health-check: ## Check health of all services
	@echo Checking API health...
	-curl -s http://localhost:8000/health
	@echo.
	@echo Checking Neo4j...
	-curl -s http://localhost:7474
	@echo.
