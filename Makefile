.PHONY: help run docker-build docker-run clean venv install lint format tree seed test

TAG ?= graph-api:dev

help:
	@echo "Commands:"
	@echo "  make venv           Create local virtualenv"
	@echo "  make install        Install requirements"
	@echo "  make run            Run FastAPI locally"
	@echo "  make docker-run     Run Docker (Neo4j + API)"
	@echo "  make seed           Run the data ingestion script"
	@echo "  make test           Run test suite"
	@echo "  make lint           Run pylint (fails if score < 9.5)"

venv:
	python3 -m venv .venv

install: venv
	. .venv/bin/activate && pip install -r requirements.txt

run:
	. .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

docker-build:
	docker build -t $(TAG) .

docker-run:
	docker-compose up --build

seed:
	docker-compose exec api python scripts/seed_data.py

test:
	pytest tests/ -v --cov=app --cov-report=term-missing

lint:
	python scripts/check_pylint_score.py

