# Makefile for ML Server Testing Suite
#
# This Makefile provides convenient commands for running tests, linting,
# and demonstrations of the ML server functionality including multi-classifier support.

.PHONY: help install install-dev test test-unit test-integration test-load test-all lint format clean demo-setup demo-load demo-monitoring server-train server-start

# Default target
help: ## Show this help message
	@echo "ML Server Testing Suite"
	@echo "======================="
	@echo ""
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Installation
install: ## Install the package
	pip install -e .

install-dev: ## Install development dependencies including test suite
	pip install -e ".[test]"

# Testing
test: test-all ## Run all tests (alias for test-all)

test-unit: ## Run unit tests only
	pytest tests/unit/ -v

test-integration: ## Run integration tests only
	pytest tests/integration/ -v

test-load: ## Run Locust load testing (requires server to be running)
	@echo "Make sure server is running: make server-start"
	@echo "Starting load test for 60 seconds..."
	locust -f tests/load/locustfile.py --host=http://localhost:8000 \
		--users 5 --spawn-rate 1 --run-time 60s --headless

test-all: ## Run all tests (unit + integration)
	pytest tests/unit/ tests/integration/ -v --cov=mlserver

test-coverage: ## Run tests with detailed coverage report
	pytest tests/ -v --cov=mlserver --cov-report=html --cov-report=term-missing --cov-report=json

test-coverage-full: ## Run comprehensive coverage analysis with metrics
	@echo "Running comprehensive coverage analysis..."
	pytest tests/ -v --cov=mlserver --cov-report=html --cov-report=term-missing --cov-report=json --cov-report=xml --cov-branch
	@echo "Generating coverage metrics report..."
	python scripts/coverage_metrics.py

coverage-report: ## Generate detailed coverage metrics report
	@if [ ! -f coverage.json ]; then \
		echo "❌ coverage.json not found. Run 'make test-coverage' first"; \
		exit 1; \
	fi
	python scripts/coverage_metrics.py

coverage-check: ## Check coverage meets minimum threshold (80%)
	@if [ ! -f coverage.json ]; then \
		echo "❌ coverage.json not found. Run 'make test-coverage' first"; \
		exit 1; \
	fi
	python scripts/coverage_metrics.py --check-threshold 80

coverage-gaps: ## Show files with coverage below 80%
	@if [ ! -f coverage.json ]; then \
		echo "❌ coverage.json not found. Run 'make test-coverage' first"; \
		exit 1; \
	fi
	python scripts/coverage_metrics.py --min-coverage 0 --show-all-files

coverage-export: ## Export coverage metrics to JSON
	@if [ ! -f coverage.json ]; then \
		echo "❌ coverage.json not found. Run 'make test-coverage' first"; \
		exit 1; \
	fi
	python scripts/coverage_metrics.py --export coverage_metrics_export.json

# Code Quality
lint: ## Run linting (if available)
	@if command -v ruff > /dev/null; then \
		ruff check mlserver/ tests/; \
	elif command -v flake8 > /dev/null; then \
		flake8 mlserver/ tests/; \
	else \
		echo "No linter found. Install ruff or flake8."; \
	fi

format: ## Format code (if available)
	@if command -v ruff > /dev/null; then \
		ruff format mlserver/ tests/ examples/; \
	elif command -v black > /dev/null; then \
		black mlserver/ tests/ examples/; \
	else \
		echo "No formatter found. Install ruff or black."; \
	fi

# Server Operations
server-train: ## Train the example model
	@echo "Training example model..."
	cd examples/example_titanic_manual_setup/ && python train_titanic.py

server-train-multi: ## Train multiple classifiers (CatBoost and RandomForest)
	@echo "Training multiple classifiers..."
	cd examples/example_titanic_manual_setup/ && /Users/peter/Desktop/enmacc/.venv/bin/python train_titanic_2_classifiers.py

server-start: ## Start the ML server with single classifier
	@echo "Starting ML server on port 8000..."
	/Users/peter/Desktop/enmacc/.venv/bin/ml_server serve examples/example_titanic_manual_setup/mlserver.yaml

server-start-catboost: ## Start CatBoost classifier from multi-classifier config
	@echo "Starting CatBoost classifier on port 8000..."
	cd examples/example_titanic_manual_setup && /Users/peter/Desktop/enmacc/.venv/bin/ml_server serve mlserver_multi_classifier.yaml --classifier catboost-survival

server-start-randomforest: ## Start RandomForest classifier from multi-classifier config
	@echo "Starting RandomForest classifier on port 8000..."
	cd examples/example_titanic_manual_setup && /Users/peter/Desktop/enmacc/.venv/bin/ml_server serve mlserver_multi_classifier.yaml --classifier randomforest-survival

server-start-bg: ## Start the ML server in background
	@echo "Starting ML server in background..."
	nohup /Users/peter/Desktop/enmacc/.venv/bin/ml_server serve examples/example_titanic_manual_setup/mlserver.yaml > server.log 2>&1 & echo $$! > server.pid
	@echo "Server PID: $$(cat server.pid)"
	@echo "Logs: tail -f server.log"

server-stop: ## Stop background server
	@if [ -f server.pid ]; then \
		kill $$(cat server.pid) && rm server.pid; \
		echo "Server stopped"; \
	else \
		echo "No server PID file found"; \
	fi

# Multi-Classifier Demo Commands
multi-test-endpoints: ## Test unified endpoints with current server
	@echo "Testing Unified Endpoints..."
	@echo ""
	@echo "1. Testing /info endpoint:"
	@curl -s http://localhost:8000/info | /Users/peter/Desktop/enmacc/.venv/bin/python -m json.tool
	@echo ""
	@echo "2. Testing /predict endpoint:"
	@curl -s -X POST http://localhost:8000/predict \
		-H "Content-Type: application/json" \
		-d '{"payload": {"records": [{"Pclass": 1, "Sex": "female", "Age": 29, "SibSp": 0, "Parch": 0, "Fare": 211.3375, "Embarked": "S", "FamilySize": 1, "IsAlone": 1, "Title": "Miss"}]}}' | /Users/peter/Desktop/enmacc/.venv/bin/python -m json.tool
	@echo ""
	@echo "3. Testing /healthz endpoint:"
	@curl -s http://localhost:8000/healthz | /Users/peter/Desktop/enmacc/.venv/bin/python -m json.tool

multi-demo-catboost: ## Demo CatBoost classifier with unified endpoints
	@echo "🚀 Starting CatBoost classifier demo..."
	@$(MAKE) server-stop 2>/dev/null || true
	@cd examples/example_titanic_manual_setup && \
		/Users/peter/Desktop/enmacc/.venv/bin/ml_server serve mlserver_multi_classifier.yaml --classifier catboost-survival --port 8000 & \
		echo $$! > ../../server.pid
	@sleep 3
	@echo "✅ CatBoost classifier started!"
	@$(MAKE) multi-test-endpoints
	@echo ""
	@echo "CatBoost demo complete! Stop with: make server-stop"

multi-demo-randomforest: ## Demo RandomForest classifier with unified endpoints
	@echo "🚀 Starting RandomForest classifier demo..."
	@$(MAKE) server-stop 2>/dev/null || true
	@cd examples/example_titanic_manual_setup && \
		/Users/peter/Desktop/enmacc/.venv/bin/ml_server serve mlserver_multi_classifier.yaml --classifier randomforest-survival --port 8000 & \
		echo $$! > ../../server.pid
	@sleep 3
	@echo "✅ RandomForest classifier started!"
	@$(MAKE) multi-test-endpoints
	@echo ""
	@echo "RandomForest demo complete! Stop with: make server-stop"

# Demonstrations
demo-setup: ## Set up example data and train model
	@echo "Setting up demo environment..."
	$(MAKE) install-dev
	$(MAKE) server-train
	@echo "Demo setup complete!"

demo-setup-multi: ## Set up multi-classifier demo environment
	@echo "Setting up multi-classifier demo environment..."
	$(MAKE) install-dev
	$(MAKE) server-train-multi
	@echo "Multi-classifier demo setup complete!"

demo-load: ## Run live metrics demo (interactive)
	@echo "Starting live metrics demo..."
	@echo "Make sure server is running: make server-start"
	python examples/load_test_demo.py --duration 120 --workers 3 --rps 2

demo-load-multi: ## Run load test with unified endpoints
	@echo "Starting load test with unified endpoints..."
	@echo "Testing /predict endpoint without version or classifier in URL..."
	python examples/load_test_demo.py --duration 60 --workers 3 --rps 2

demo-load-heavy: ## Run heavy load demo
	@echo "Starting heavy load demo..."
	python examples/load_test_demo.py --duration 60 --workers 10 --rps 5

demo-monitoring: ## Start monitoring stack (Prometheus + Grafana)
	@echo "Starting monitoring stack..."
	@echo "Stopping any existing containers first..."
	@docker-compose -f docker-compose.monitoring.yml down 2>/dev/null || true
	@echo "Starting fresh monitoring containers..."
	docker-compose -f docker-compose.monitoring.yml up -d
	@echo ""
	@echo "Services started:"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Grafana: http://localhost:3000 (admin/admin123)"
	@echo "  ML Server metrics: http://localhost:8000/metrics"
	@echo ""
	@echo "Stop with: make demo-monitoring-stop"

demo-monitoring-stop: ## Stop monitoring stack
	docker-compose -f docker-compose.monitoring.yml down

demo-full: ## Complete demo: setup + server + monitoring + load test
	@echo "Starting complete demo setup..."
	@echo "Cleaning up any previous demo..."
	@$(MAKE) clean-demo 2>/dev/null || true
	$(MAKE) demo-setup
	$(MAKE) server-start-bg
	@echo "Waiting for server to start..."
	@sleep 5
	$(MAKE) demo-monitoring
	@echo "Waiting for monitoring to start..."
	@sleep 10
	@echo ""
	@echo "🚀 Demo environment ready!"
	@echo "  ML Server: http://localhost:8000/docs"
	@echo "  Metrics: http://localhost:8000/metrics"
	@echo "  Info: http://localhost:8000/info"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Grafana: http://localhost:3000"
	@echo ""
	@echo "Running load test..."
	$(MAKE) demo-load
	@echo ""
	@echo "Demo complete! Clean up with: make clean-demo"

demo-multi-full: ## Complete multi-classifier demo with both classifiers
	@echo "🎯 Starting complete multi-classifier demo..."
	@echo "Cleaning up any previous demo..."
	@$(MAKE) clean-demo 2>/dev/null || true
	@echo ""
	@echo "1️⃣ Setting up multi-classifier environment..."
	$(MAKE) demo-setup-multi
	@echo ""
	@echo "2️⃣ Testing CatBoost classifier..."
	$(MAKE) multi-demo-catboost
	@sleep 5
	@echo ""
	@echo "3️⃣ Testing RandomForest classifier..."
	$(MAKE) multi-demo-randomforest
	@sleep 5
	@echo ""
	@echo "✅ Multi-classifier demo complete!"
	@echo "Both classifiers tested with unified endpoints (/predict, /info)"
	@echo "Clean up with: make clean-demo"

clean-demo: ## Clean up demo environment
	@echo "Cleaning up demo environment..."
	@$(MAKE) server-stop 2>/dev/null || true
	@$(MAKE) demo-monitoring-stop 2>/dev/null || true
	@echo "Demo environment cleaned up"

# Utility
clean: ## Clean up generated files
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf *.log
	rm -rf server.pid
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete

check-server: ## Check if server is healthy
	@echo "Checking server health..."
	@curl -s http://localhost:8000/healthz | python -m json.tool || echo "Server not responding"

check-info: ## Check classifier info endpoint
	@echo "Checking classifier info..."
	@curl -s http://localhost:8000/info | python -m json.tool || echo "Info not available"

show-metrics: ## Display current server metrics
	@echo "Current server metrics:"
	@curl -s http://localhost:8000/metrics || echo "Metrics not available"

debug-monitoring: ## Debug monitoring stack connectivity
	@echo "🔍 Debugging Monitoring Stack"
	@echo "==============================="
	@echo ""
	@echo "1. Checking ML Server health..."
	@curl -s http://localhost:8000/healthz | python -m json.tool 2>/dev/null || echo "   ❌ ML Server not responding"
	@echo ""
	@echo "2. Checking ML Server info..."
	@curl -s http://localhost:8000/info | python -c "import sys,json; d=json.load(sys.stdin); print(f\"   Repository: {d.get('repository')}\"); print(f\"   Classifier: {d.get('classifier')}\"); print(f\"   Version: {d.get('version')}\")" 2>/dev/null || echo "   ❌ ML Server info not available"
	@echo ""
	@echo "3. Checking ML Server metrics..."
	@curl -s http://localhost:8000/metrics | head -5 2>/dev/null || echo "   ❌ ML Server metrics not available"
	@echo ""
	@echo "4. Checking Prometheus targets..."
	@curl -s http://localhost:9090/api/v1/targets 2>/dev/null | python -c "import sys,json; data=json.load(sys.stdin); [print(f\"   {t['labels']['job']}: {'✅' if t['health']=='up' else '❌'} {t['health']}\") for t in data['data']['activeTargets']]" 2>/dev/null || echo "   ❌ Prometheus not responding"
	@echo ""
	@echo "5. Checking Grafana datasource..."
	@curl -s http://localhost:3000/api/datasources 2>/dev/null | python -c "import sys,json; data=json.load(sys.stdin); [print(f\"   {ds['name']}: {'✅' if ds['url'] else '❌'} {ds['url']}\") for ds in data]" 2>/dev/null || echo "   ❌ Grafana not responding (try: admin/admin123)"
	@echo ""
	@echo "📍 Service URLs:"
	@echo "   ML Server: http://localhost:8000"
	@echo "   Prometheus: http://localhost:9090"
	@echo "   Grafana: http://localhost:3000"

check-prometheus-targets: ## Check Prometheus target status
	@echo "Prometheus Target Status:"
	@curl -s http://localhost:9090/api/v1/targets | python -c "import sys,json; data=json.load(sys.stdin); [print(f\"  {t['labels']['job']}: {t['health']} - {t['lastScrapeUrl']}\") for t in data['data']['activeTargets']]" 2>/dev/null || echo "Prometheus not available"

# Advanced Testing
test-stress: ## Run stress test with high concurrency
	locust -f tests/load/locustfile.py --host=http://localhost:8000 \
		--users 50 --spawn-rate 10 --run-time 300s --headless

test-endurance: ## Run long endurance test
	locust -f tests/load/locustfile.py --host=http://localhost:8000 \
		--users 10 --spawn-rate 2 --run-time 1800s --headless

# CI/CD helpers
ci-test: ## Run tests suitable for CI environment
	pytest tests/unit/ tests/integration/ -v --tb=short --maxfail=5

ci-lint: ## Run linting for CI
	@if command -v ruff > /dev/null; then \
		ruff check mlserver/ tests/ --output-format=github; \
	else \
		echo "ruff not found, install for CI"; exit 1; \
	fi

# Container Operations
container-version: ## Show version information for container builds
	@echo "Checking version information for container builds..."
	/Users/peter/Desktop/enmacc/.venv/bin/ml_server version --path examples/example_titanic_manual_setup/

container-build: ## Build Docker container from example
	@echo "Building Docker container from examples..."
	@if ! command -v docker > /dev/null; then \
		echo "❌ Docker is not available. Please install Docker."; \
		exit 1; \
	fi
	/Users/peter/Desktop/enmacc/.venv/bin/ml_server build --path examples/example_titanic_manual_setup/ --verbose

container-build-catboost: ## Build Docker container for CatBoost classifier
	@echo "Building Docker container for CatBoost classifier..."
	cd examples/example_titanic_manual_setup && \
		/Users/peter/Desktop/enmacc/.venv/bin/ml_server build --classifier catboost-survival

container-build-randomforest: ## Build Docker container for RandomForest classifier
	@echo "Building Docker container for RandomForest classifier..."
	cd examples/example_titanic_manual_setup && \
		/Users/peter/Desktop/enmacc/.venv/bin/ml_server build --classifier randomforest-survival

container-images: ## List built container images
	@echo "Listing Docker images for this project..."
	/Users/peter/Desktop/enmacc/.venv/bin/ml_server images --path examples/example_titanic_manual_setup/

container-clean: ## Remove built container images
	@echo "Cleaning up Docker container images..."
	/Users/peter/Desktop/enmacc/.venv/bin/ml_server clean --path examples/example_titanic_manual_setup/ --force

container-test: ## Build and test container functionality
	@echo "Testing complete container workflow..."
	$(MAKE) container-build
	@echo "Verifying built containers..."
	$(MAKE) container-images
	@echo "Testing container startup (if images exist)..."
	@IMAGE_ID=$$(docker images -q --filter "reference=*titanic*" | head -1); \
	if [ -n "$$IMAGE_ID" ]; then \
		echo "Starting container test on port 8012..."; \
		timeout 30s docker run --rm -p 8012:8000 $$IMAGE_ID & \
		sleep 10; \
		curl -f http://localhost:8012/healthz || echo "Container health check failed"; \
		pkill -f "docker run.*8012" || true; \
	else \
		echo "No container images found to test"; \
	fi

demo-container: ## Complete container demo workflow
	@echo "🚀 Starting complete container demo..."
	@echo "1. Checking version information..."
	$(MAKE) container-version
	@echo ""
	@echo "2. Building container..."
	$(MAKE) container-build
	@echo ""
	@echo "3. Listing built images..."
	$(MAKE) container-images
	@echo ""
	@echo "4. Testing container functionality..."
	$(MAKE) container-test
	@echo ""
	@echo "✅ Container demo complete!"
	@echo "Clean up with: make container-clean"

# Development helpers
dev-setup: ## Complete development setup
	$(MAKE) install-dev
	$(MAKE) demo-setup
	@echo ""
	@echo "Development environment ready!"
	@echo "Run 'make test' to run tests"
	@echo "Run 'make server-start' to start server"

watch-tests: ## Watch for changes and run tests (requires entr)
	@if command -v entr > /dev/null; then \
		find mlserver/ tests/ -name "*.py" | entr -c make test-unit; \
	else \
		echo "Install entr for watch functionality: brew install entr"; \
	fi