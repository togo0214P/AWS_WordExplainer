UVICORN ?= .venv/bin/uvicorn
HOST ?= 127.0.0.1
PORT ?= 8080

.PHONY: run
run:
	$(UVICORN) app.main:app --reload --host $(HOST) --port $(PORT) --log-level info
