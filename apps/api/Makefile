# Cawnex API - ULTRA STRICT Development Commands

.PHONY: help install dev-install type-check lint format test security clean build
.DEFAULT_GOAL := help

# Variables - CI-aware paths
ifeq ($(CI),true)
    # In CI environment, use globally installed tools
    PYTHON := python
    PIP := pip
    MYPY := mypy
    BLACK := black
    ISORT := isort
    FLAKE8 := flake8
    BANDIT := bandit
    PYTEST := pytest
    PIP_AUDIT := pip-audit
    PRECOMMIT := pre-commit
else
    # Local development, use venv
    PYTHON := venv/bin/python
    PIP := venv/bin/pip
    MYPY := venv/bin/mypy
    BLACK := venv/bin/black
    ISORT := venv/bin/isort
    FLAKE8 := venv/bin/flake8
    BANDIT := venv/bin/bandit
    PYTEST := venv/bin/pytest
    PIP_AUDIT := venv/bin/pip-audit
    PRECOMMIT := venv/bin/pre-commit
endif

SRC_DIR := src
TEST_DIR := tests
VENV_DIR := venv

help: ## Show this help message
	@echo "Cawnex API - Development Commands"
	@echo "================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	$(PIP) install -e .

dev-install: ## Install development dependencies
	$(PIP) install -e ".[dev,test]"
	pre-commit install

# ================================
# TYPE CHECKING - ULTRA STRICT
# ================================
type-check: ## Run MyPy type checking (STRICT)
	@echo "🔍 Running MyPy type checking..."
	$(MYPY) $(SRC_DIR) --strict --show-error-codes --pretty
	@echo "✅ Type checking passed!"

type-check-report: ## Generate MyPy type checking HTML report
	@echo "📊 Generating MyPy HTML report..."
	$(MYPY) $(SRC_DIR) --strict --html-report mypy-report
	@echo "📄 Report generated at: mypy-report/index.html"

# ================================
# LINTING - ULTRA STRICT
# ================================
lint: ## Run all linters (flake8, bandit, etc.)
	@echo "🔍 Running Flake8 linting..."
	$(FLAKE8) $(SRC_DIR) --max-line-length=88 --max-complexity=10
	@echo "🔒 Running Bandit security checks..."
	$(BANDIT) -r $(SRC_DIR) -f json -o bandit-report.json
	@echo "✅ All linting passed!"

lint-fix: ## Auto-fix linting issues where possible
	@echo "🔧 Running isort..."
	$(ISORT) $(SRC_DIR) $(TEST_DIR)
	@echo "🔧 Running Black..."
	$(BLACK) $(SRC_DIR) $(TEST_DIR)
	@echo "✅ Auto-fixing complete!"

# ================================
# FORMATTING - ULTRA STRICT
# ================================
format: ## Format code with Black and sort imports with isort
	@echo "📝 Formatting code..."
	$(BLACK) $(SRC_DIR) $(TEST_DIR) --line-length=88
	$(ISORT) $(SRC_DIR) $(TEST_DIR) --profile black
	@echo "✅ Formatting complete!"

format-check: ## Check if code is properly formatted
	@echo "📝 Checking code formatting..."
	$(BLACK) $(SRC_DIR) $(TEST_DIR) --check --line-length=88
	$(ISORT) $(SRC_DIR) $(TEST_DIR) --check-only --profile black
	@echo "✅ Code is properly formatted!"

# ================================
# TESTING - COVERAGE REQUIRED
# ================================
test: ## Run tests with coverage (min 80%)
	@echo "🧪 Running tests with coverage..."
	$(PYTEST) --cov=$(SRC_DIR) --cov-report=term-missing --cov-fail-under=80
	@echo "✅ All tests passed!"

test-fast: ## Run tests without coverage
	@echo "🧪 Running fast tests..."
	$(PYTEST) -x -v
	@echo "✅ Fast tests passed!"

test-report: ## Generate HTML test coverage report
	@echo "📊 Generating test coverage report..."
	$(PYTEST) --cov=$(SRC_DIR) --cov-report=html
	@echo "📄 Report generated at: htmlcov/index.html"

# ================================
# SECURITY - ULTRA STRICT
# ================================
security: ## Run security checks
	@echo "🔒 Running security checks..."
	$(BANDIT) -r $(SRC_DIR) -f json -o bandit-report.json
	@echo "🔍 Checking for known vulnerabilities..."
	$(PIP_AUDIT)
	@echo "✅ Security checks passed!"

# ================================
# FULL QUALITY CHECK
# ================================
quality: format-check type-check lint test security ## Run ALL quality checks
	@echo "🏆 ALL QUALITY CHECKS PASSED!"
	@echo "✅ Code is production-ready!"

ci: quality ## Run CI pipeline (same as quality)

# ================================
# DEVELOPMENT
# ================================
dev: ## Start development server
	@echo "🚀 Starting development server..."
ifeq ($(CI),true)
	@echo "⚠️  Development server not available in CI environment"
else
	$(VENV_DIR)/bin/uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
endif

dev-debug: ## Start development server with debug logging
	@echo "🐛 Starting development server with debug..."
ifeq ($(CI),true)
	@echo "⚠️  Development server not available in CI environment"
else
	$(VENV_DIR)/bin/uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug
endif

# ================================
# BUILD & DEPLOYMENT
# ================================
build: quality ## Build distribution (after quality checks)
	@echo "📦 Building distribution..."
	$(PYTHON) -m build
	@echo "✅ Build complete!"

build-lambda: ## Build for AWS Lambda deployment
	@echo "📦 Building for Lambda..."
	rm -rf dist/
	mkdir -p dist/
	cp -r $(SRC_DIR)/* dist/
	cp handler.py dist/
	$(PIP) install -r requirements.txt -t dist/
	@echo "✅ Lambda build complete!"

# ================================
# CLEANUP
# ================================
clean: ## Clean build artifacts and cache
	@echo "🧹 Cleaning up..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf mypy-report/
	rm -f bandit-report.json
	rm -f .coverage
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete
	@echo "✅ Cleanup complete!"

# ================================
# PRE-COMMIT HOOKS
# ================================
pre-commit: ## Run pre-commit hooks on all files
	@echo "🔍 Running pre-commit hooks..."
	$(PRECOMMIT) run --all-files
	@echo "✅ Pre-commit hooks passed!"

install-hooks: ## Install pre-commit hooks
	@echo "🪝 Installing pre-commit hooks..."
ifeq ($(CI),true)
	@echo "⚠️  Pre-commit hooks not installed in CI environment"
else
	$(PRECOMMIT) install
	@echo "✅ Hooks installed!"
endif
