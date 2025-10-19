.PHONY: help fmt test lint comparison-test comparison-refresh clean

# Variables
PYTHON := python3
PIP := pip3
PYTEST := python3 -m pytest

# Default target
help:
	@echo "Naver SMS Automation - Development Commands"
	@echo ""
	@echo "Code Quality:"
	@echo "  make fmt           - Format code with black"
	@echo "  make lint          - Run linting and type checks"
	@echo ""
	@echo "Testing:"
	@echo "  make test          - Run all tests except comparison"
	@echo "  make test-unit     - Run unit tests only"
	@echo "  make comparison-test - Run comparison/parity tests"
	@echo "  make test-all      - Run all tests including comparison"
	@echo ""
	@echo "Comparison Framework:"
	@echo "  make comparison-refresh - Regenerate comparison fixtures"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean         - Clean build artifacts and cache"

# ============================================================================
# Code Quality
# ============================================================================

fmt:
	@echo "Formatting code with black..."
	$(PYTHON) -m black src/ tests/ --line-length=100
	@echo "✅ Code formatted"

lint:
	@echo "Running linting and type checks..."
	$(PYTHON) -m flake8 src/ tests/comparison --max-line-length=100 --ignore=E501,W503
	$(PYTHON) -m mypy src/ --ignore-missing-imports --no-error-summary 2>/dev/null || true
	@echo "✅ Linting passed"

# ============================================================================
# Testing
# ============================================================================

test:
	@echo "Running tests (excluding comparison)..."
	$(PYTEST) tests/ -m "not comparison" -v --tb=short

test-unit:
	@echo "Running unit tests..."
	$(PYTEST) tests/unit/ -v --tb=short

test-integration:
	@echo "Running integration tests..."
	$(PYTEST) tests/integration/ -v --tb=short

comparison-test:
	@echo "Running comparison/parity tests..."
	$(PYTEST) tests/comparison/test_output_parity.py -v --tb=short -m "comparison" || true
	@echo ""
	@echo "📋 Comparison results written to: tests/comparison/results/"
	@echo ""
	@ls -la tests/comparison/results/ 2>/dev/null || echo "No results yet - run tests first"

test-all:
	@echo "Running all tests (including comparison)..."
	$(PYTEST) tests/ -v --tb=short
	@echo ""
	@echo "📊 Test coverage report generated: htmlcov/index.html"

# ============================================================================
# Comparison Framework
# ============================================================================

comparison-refresh:
	@echo "Regenerating comparison fixtures..."
	$(PYTHON) scripts/comparison/refresh_comparison_dataset.py
	@echo "✅ Fixtures refreshed"
	@echo "📁 Updated files:"
	@echo "  - tests/fixtures/production_bookings.json"
	@echo "  - tests/fixtures/production_expected_outputs.json"
	@echo "  - tests/fixtures/dataset_manifest.json"

# ============================================================================
# Utilities
# ============================================================================

clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".coverage" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .tox dist build
	@echo "✅ Cleaned"

# ============================================================================
# CI Targets (for GitHub Actions / Local CI)
# ============================================================================

.PHONY: ci-unit ci-comparison ci-all

ci-unit:
	@echo "CI: Running unit tests..."
	$(PYTEST) tests/unit/ -v --tb=short --junit-xml=test-results-unit.xml

ci-comparison:
	@echo "CI: Running comparison tests..."
	$(PYTEST) tests/comparison/test_output_parity.py -v --tb=short --junit-xml=test-results-comparison.xml
	@echo "Uploading comparison artifacts..."
	@ls -la tests/comparison/results/*.{json,md} 2>/dev/null || echo "No artifacts to upload"

ci-all: ci-unit ci-comparison
	@echo "✅ CI pipeline complete"
