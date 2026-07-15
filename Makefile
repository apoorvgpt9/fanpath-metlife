.PHONY: lint test verify-graph verify-docs docstrings typecheck audit run deploy

REGION ?= asia-south1
SERVICE ?= fanpath-metlife

lint:
	ruff check .
	python scripts/check_function_length.py

test:
	pytest --cov=app --cov-report=term-missing --cov-fail-under=95

verify-graph:
	python scripts/verify_graph.py

verify-docs:
	python scripts/verify_docs.py

docstrings:
	python -m interrogate app -vv

typecheck:
	python -m mypy app

audit:
	pip-audit

run:
	uvicorn app.main:app --reload --port 8080

deploy:
	gcloud run deploy $(SERVICE) --source . --region $(REGION) --allow-unauthenticated
