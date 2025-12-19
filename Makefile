.PHONY: help build up down logs restart auth clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build the Docker image
	docker-compose build

up: ## Start the fetcher in detached mode
	docker-compose up -d

down: ## Stop and remove containers
	docker-compose down

logs: ## View logs (follow mode)
	docker-compose logs -f

restart: ## Restart the fetcher
	docker-compose restart

auth: ## Run interactive authentication
	docker-compose run --rm infomentor-fetcher auth

clean: ## Remove containers, volumes, and images
	docker-compose down -v
	docker rmi infomentor-rev-infomentor-fetcher 2>/dev/null || true

status: ## Show container status
	docker-compose ps

shell: ## Open a shell in the container
	docker-compose run --rm infomentor-fetcher /bin/bash
