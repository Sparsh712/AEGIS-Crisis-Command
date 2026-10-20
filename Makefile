SHELL := /bin/sh

FRONTEND_DIR := frontend
PYTHON := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: install test build dev api docker-build docker-run clean

install:
	python3 -m venv .venv
	$(PIP) install --requirement backend/requirements.lock
	npm --prefix $(FRONTEND_DIR) ci

test:
	$(PYTHON) -m pytest backend/tests -q
	npm --prefix $(FRONTEND_DIR) run typecheck
	npm --prefix $(FRONTEND_DIR) run build

build:
	npm --prefix $(FRONTEND_DIR) run build

dev:
	npm --prefix $(FRONTEND_DIR) run dev

api:
	$(PYTHON) -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload

docker-build:
	docker build -t aegis-level-0 .

docker-run:
	docker run --rm -p 8000:8000 aegis-level-0

clean:
	python -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ['frontend/.next', 'frontend/out']]"
