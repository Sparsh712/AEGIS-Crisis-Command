SHELL := /bin/sh

FRONTEND_DIR := frontend
PYTHON_BIN ?= python3.11
PYTHON := .venv/bin/python
PIP := .venv/bin/pip
NODE_VERSION := 22.14.0

.PHONY: check-runtime ensure-env install test build dev api docker-build docker-run clean

check-runtime:
	@command -v $(PYTHON_BIN) >/dev/null 2>&1 || { echo "Missing $(PYTHON_BIN); install Python 3.11.11 or activate the pinned runtime."; exit 1; }
	@$(PYTHON_BIN) -c "import sys; assert sys.version_info[:2] == (3, 11), f'Expected Python 3.11, found {sys.version.split()[0]}'"
	@test "$$(node --version)" = "v$(NODE_VERSION)" || { echo "Expected Node $(NODE_VERSION); activate .nvmrc before building."; exit 1; }

ensure-env: check-runtime
	@if [ ! -x "$(PYTHON)" ] || ! "$(PYTHON)" -c "import fastapi, httpx, pydantic, pytest, sse_starlette" >/dev/null 2>&1; then \
		echo "Preparing the project-local Python environment..."; \
		rm -rf .venv; \
		$(PYTHON_BIN) -m venv .venv; \
		$(PIP) install --requirement backend/requirements.lock; \
	fi
	@if [ ! -x "$(FRONTEND_DIR)/node_modules/.bin/next" ]; then npm --prefix $(FRONTEND_DIR) ci; fi

install: check-runtime
	$(PYTHON_BIN) -m venv .venv
	$(PIP) install --requirement backend/requirements.lock
	npm --prefix $(FRONTEND_DIR) ci

test: ensure-env
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
	docker build -t aegis:local .

docker-run:
	docker run --rm -p 8000:8000 aegis:local

clean:
	python -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ['frontend/.next', 'frontend/out']]"
