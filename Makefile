.PHONY: help install test test-cov lint format clean run docker-build docker-up docker-down migrate upgrade

help:
	@echo "Family Finance Bot - Makefile Commands"
	@echo ""
	@echo "Development:"
	@echo "  make install      - Install dependencies"
	@echo "  make test         - Run tests"
	@echo "  make test-cov     - Run tests with coverage"
	@echo "  make lint         - Run linters (flake8, mypy)"
	@echo "  make format       - Format code with black"
	@echo "  make run          - Run the bot locally"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build - Build Docker images"
	@echo "  make docker-up    - Start containers"
	@echo "  make docker-down  - Stop containers"
	@echo "  make docker-logs  - View container logs"
	@echo ""
	@echo "Database:"
	@echo "  make migrate      - Create new migration"
	@echo "  make upgrade      - Run migrations"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean        - Remove temporary files"

install:
	pip install --upgrade pip
	pip install -r requirements.txt

test:
	pytest -v

test-cov:
	pytest --cov=bot --cov=config --cov-report=html --cov-report=term

lint:
	flake8 bot/ tests/ config/ --max-line-length=100 --exclude=__pycache__,venv,alembic
	mypy bot/ --ignore-missing-imports

format:
	black bot/ tests/ config/ main.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache .mypy_cache htmlcov .coverage
	rm -rf *.egg-info dist build

run:
	python main.py

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f bot

migrate:
	alembic revision --autogenerate -m "$(MSG)"

upgrade:
	alembic upgrade head

# Production deployment helpers
deploy-systemd:
	@echo "Deploying to systemd..."
	sudo cp family-finance-bot.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable family-finance-bot
	sudo systemctl restart family-finance-bot
	@echo "Deployment complete. Check status with: sudo systemctl status family-finance-bot"

logs-systemd:
	sudo journalctl -u family-finance-bot -f
