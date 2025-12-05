.PHONY: help install-server install-sdk test run-server docker-build docker-up docker-down clean

help:
	@echo "RunAgent Pulse - Development Commands"
	@echo ""
	@echo "  make install-server    Install server dependencies"
	@echo "  make install-sdk        Install SDK dependencies"
	@echo "  make test               Run tests"
	@echo "  make run-server         Run server locally"
	@echo "  make docker-build       Build Docker image"
	@echo "  make docker-up          Start Docker container"
	@echo "  make docker-down        Stop Docker container"
	@echo "  make clean              Clean temporary files"

install-server:
	cd server && pip install -r requirements.txt

install-sdk:
	cd sdk && pip install -r requirements.txt

test:
	pip install -r tests/requirements.txt
	pytest tests/ -v

run-server:
	cd server && python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload

docker-build:
	docker build -t runagent/pulse:latest .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.db" -delete
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov


