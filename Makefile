SHELL := /bin/sh

CONTAINER_ENGINE ?= $(shell command -v podman >/dev/null 2>&1 && echo podman || echo docker)
IMAGE_NAME ?= openapi-api-gateway
IMAGE_TAG ?= latest
CONTAINER_NAME ?= openapi-api-gateway
PORT ?= 8000
GATEWAY_PORT ?= $(PORT)
ENV_FILE ?= .env
CONFIG_PROFILE ?= local
COMPOSE_FILE ?= docker-compose.dev.yml
COMPANION_OPENAPI ?= http://127.0.0.1:8068/openapi.json

ifeq ($(origin GATEWAY_CONFIG_PATH), undefined)
ifeq ($(CONFIG_PROFILE),container)
GATEWAY_CONFIG_PATH := config/gateway.container.yaml
else
GATEWAY_CONFIG_PATH := config/gateway.yaml
endif
endif

RUN_ENV := $(if $(wildcard $(ENV_FILE)),--env-file $(ENV_FILE),)

.PHONY: help build run run-local stop logs shell test test-container fmt clean check-companion-parity compose-up compose-down compose-logs

help:
	@echo "Targets:"
	@echo "  make build           Build container image"
	@echo "  make run             Run gateway container with CONFIG_PROFILE=local|container"
	@echo "  make run-local       Run gateway with uv and CONFIG_PROFILE=local|container"
	@echo "  make stop            Stop and remove container"
	@echo "  make logs            Follow container logs"
	@echo "  make shell           Open shell in running container"
	@echo "  make test            Run local pytest suite with uv"
	@echo "  make test-container  Run tests in container image"
	@echo "  make check-companion-parity  Compare selected gateway profile to companion OpenAPI"
	@echo "  make compose-up      Build and start companion backend plus gateway with Docker Compose"
	@echo "  make compose-down    Stop the dev compose stack"
	@echo "  make compose-logs    Follow logs for the dev compose stack"
	@echo "  make fmt             Run ruff format checks"
	@echo "  make clean           Remove image and stopped container"

build:
	$(CONTAINER_ENGINE) build -t $(IMAGE_NAME):$(IMAGE_TAG) -f Dockerfile .

run:
	$(MAKE) stop >/dev/null 2>&1 || true
	$(CONTAINER_ENGINE) run -d \
		--name $(CONTAINER_NAME) \
		-p $(PORT):$(GATEWAY_PORT) \
		-e GATEWAY_CONFIG_PATH=$(GATEWAY_CONFIG_PATH) \
		-e GATEWAY_PORT=$(GATEWAY_PORT) \
		$(RUN_ENV) \
		$(IMAGE_NAME):$(IMAGE_TAG)
	@echo "Gateway is running on http://127.0.0.1:$(PORT) using $(GATEWAY_CONFIG_PATH) (bind port $(GATEWAY_PORT))"

run-local:
	GATEWAY_CONFIG_PATH=$(GATEWAY_CONFIG_PATH) GATEWAY_PORT=$(GATEWAY_PORT) uv run python -m gateway_framework.main

stop:
	-$(CONTAINER_ENGINE) rm -f $(CONTAINER_NAME)

logs:
	$(CONTAINER_ENGINE) logs -f $(CONTAINER_NAME)

shell:
	$(CONTAINER_ENGINE) exec -it $(CONTAINER_NAME) sh

test:
	uv run pytest -q

test-container:
	$(CONTAINER_ENGINE) run --rm $(IMAGE_NAME):$(IMAGE_TAG) uv run pytest -q

check-companion-parity:
	uv run python -m gateway_framework.companion --config $(GATEWAY_CONFIG_PATH) --openapi $(COMPANION_OPENAPI)

compose-up:
	$(CONTAINER_ENGINE) compose -f $(COMPOSE_FILE) up --build -d lta-datamall-api
	$(MAKE) check-companion-parity CONFIG_PROFILE=container
	$(CONTAINER_ENGINE) compose -f $(COMPOSE_FILE) up --build -d gateway

compose-down:
	$(CONTAINER_ENGINE) compose -f $(COMPOSE_FILE) down --remove-orphans

compose-logs:
	$(CONTAINER_ENGINE) compose -f $(COMPOSE_FILE) logs -f

fmt:
	uv run ruff check .

clean: stop
	-$(CONTAINER_ENGINE) rmi $(IMAGE_NAME):$(IMAGE_TAG)
