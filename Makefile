SHELL := /bin/sh

CONTAINER_ENGINE ?= $(shell command -v podman >/dev/null 2>&1 && echo podman || echo docker)
IMAGE_NAME ?= openapi-api-gateway
IMAGE_TAG ?= latest
CONTAINER_NAME ?= openapi-api-gateway
PORT ?= 8000
ENV_FILE ?= .env

RUN_ENV := $(if $(wildcard $(ENV_FILE)),--env-file $(ENV_FILE),)

.PHONY: help build run stop logs shell test test-container fmt clean

help:
	@echo "Targets:"
	@echo "  make build           Build container image"
	@echo "  make run             Run gateway container"
	@echo "  make stop            Stop and remove container"
	@echo "  make logs            Follow container logs"
	@echo "  make shell           Open shell in running container"
	@echo "  make test            Run local pytest suite with uv"
	@echo "  make test-container  Run tests in container image"
	@echo "  make fmt             Run ruff format checks"
	@echo "  make clean           Remove image and stopped container"

build:
	$(CONTAINER_ENGINE) build -t $(IMAGE_NAME):$(IMAGE_TAG) -f Dockerfile .

run:
	$(MAKE) stop >/dev/null 2>&1 || true
	$(CONTAINER_ENGINE) run -d \
		--name $(CONTAINER_NAME) \
		-p $(PORT):8000 \
		$(RUN_ENV) \
		$(IMAGE_NAME):$(IMAGE_TAG)
	@echo "Gateway is running on http://127.0.0.1:$(PORT)"

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

fmt:
	uv run ruff check .

clean: stop
	-$(CONTAINER_ENGINE) rmi $(IMAGE_NAME):$(IMAGE_TAG)
