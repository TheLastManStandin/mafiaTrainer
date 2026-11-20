PYTHON ?= python3
WEB_HOST ?= 0.0.0.0
WEB_PORT ?= 8000

.PHONY: web
web:
	$(PYTHON) main.py --web --host "$(WEB_HOST)" --port "$(WEB_PORT)"
