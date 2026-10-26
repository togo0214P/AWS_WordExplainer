UVICORN ?= .venv/bin/uvicorn
HOST ?= 127.0.0.1
PORT ?= 8080

.PHONY: run view view-build
run:
	$(UVICORN) app.main:app --reload --host $(HOST) --port $(PORT) --log-level info

view:
	cd view && npm run dev

view-build:
	cd view && npm run build
