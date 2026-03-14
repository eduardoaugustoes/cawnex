.PHONY: build clean dev test

# Build deployable artifact for Lambda (CDK expects apps/api/dist/)
build:
	rm -rf dist
	mkdir -p dist
	python3 -m pip install -r requirements.txt -t dist --quiet
	cp handler.py dist/
	cp -r src dist/

# Clean build artifacts
clean:
	rm -rf dist __pycache__ .pytest_cache
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Local development server
dev:
	uvicorn src.main:app --reload --port 8000

# Run tests
test:
	python3 -m pytest tests/ -v
