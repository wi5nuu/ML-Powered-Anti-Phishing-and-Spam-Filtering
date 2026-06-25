.PHONY: help install test lint run-dashboard run-worker run-classifier seed-admin train build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	pip install -r requirements.txt -r requirements-dev.txt
	python -m nltk.downloader punkt stopwords words -q

test: ## Run test suite
	pytest --cov=classifier --cov=decision_engine --cov=database --cov=worker --cov-report=term-missing -v

test-coverage: ## Run tests with HTML coverage report
	pytest --cov=classifier --cov=decision_engine --cov=database --cov=worker --cov-report=html -v

lint: ## Run all linters
	black --check --diff . || true
	isort --check-only --diff . || true
	ruff check . || true

format: ## Auto-format code
	black .
	isort .

typecheck: ## Run mypy type checking
	mypy classifier/ decision_engine/ dashboard/ worker/ --ignore-missing-imports || true

run-classifier: ## Start classifier API service
	uvicorn classifier.predict:app --host 0.0.0.0 --port 8001 --reload

run-dashboard: ## Start dashboard web UI
	uvicorn dashboard.app:app --host 0.0.0.0 --port 8081 --reload

run-worker: ## Start pipeline worker
	python -m worker.pipeline_worker

run-ingestion: ## Start email ingestion runner
	python scripts/run_ingestion.py

seed-emails: ## Seed test emails to Mailpit
	python scripts/seed_test_emails.py

train: ## Train supervised model
	python scripts/train_real_model.py

train-unsupervised: ## Train unsupervised anomaly detector
	python scripts/train_unsupervised.py

generate-report: ## Generate weekly PDF security report
	python scripts/generate_report.py

network-graph: ## Generate email network graph
	python scripts/network_graph.py

wordcloud: ## Generate word cloud comparison
	python scripts/wordcloud_gen.py

drift-check: ## Run drift detection
	python scripts/drift_monitor.py --check

load-test: ## Run load tests (requires Locust)
	locust -f tests/locustfile.py --host=http://localhost:8001 --headless -u 50 -r 10 --run-time 30s

docker-up: ## Start all Docker services
	docker compose up -d

docker-down: ## Stop all Docker services
	docker compose down

docker-build: ## Build all Docker images
	docker compose build

clean: ## Clean cache and temp files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/ reports/*.pdf reports/*.html 2>/dev/null || true

db-init: ## Initialize database with schema
	python -c "from database.models import init_db; init_db()"

seed-admin: ## Seed admin user
	python -c "from dashboard.app import seed_admin; seed_admin()"

all: install test lint docker-build ## Full pipeline: install → test → lint → build
