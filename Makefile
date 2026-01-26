COMPOSE = docker compose -f Infra/docker-compose.yml

.PHONY: up down logs ps build

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

build:
	$(COMPOSE) build
