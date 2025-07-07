# Claude Orchestrator Makefile

.PHONY: help install test coverage lint type-check security clean docs

help:
	@echo "Available commands:"
	@echo "  make install      Install dependencies"
	@echo "  make test         Run tests"
	@echo "  make coverage     Run tests with coverage report"
	@echo "  make lint         Run linting checks"
	@echo "  make type-check   Run type checking"
	@echo "  make security     Run security checks"
	@echo "  make clean        Clean up generated files"
	@echo "  make docs         Generate documentation"
	@echo "  make all          Run all checks"

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v

coverage:
	pytest --cov=claude_orchestrator --cov-report=html --cov-report=term-missing tests/
	@echo "Coverage report generated in htmlcov/index.html"

lint:
	ruff check .

type-check:
	mypy claude_orchestrator --ignore-missing-imports

security:
	@echo "Running security audit..."
	python -m claude_orchestrator.main security-audit

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/

docs:
	cd docs && make html
	@echo "Documentation generated in docs/_build/html/index.html"

all: lint type-check test coverage security
	@echo "All checks completed!"