# EII — ERP Incident Intelligence
# Makefile for Unix-like shells (Git Bash, WSL, macOS, Linux)

.PHONY: install run test docker-build docker-run clean

PYTHON ?= python
PIP    ?= pip

install:
	$(PIP) install -r requirements.txt

run:
	$(PYTHON) app.py

api:
	uvicorn api:app --host 0.0.0.0 --port 8000 --reload

test:
	$(PYTHON) -m pytest tests/ -v --tb=short

test-all:
	$(PYTHON) -m pytest tests/ smartrouter/tests/ -v --tb=short

docker-build:
	docker build -t eii .

docker-run:
	docker run -p 7860:7860 --env-file .env eii

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -f eii_incidents.db
