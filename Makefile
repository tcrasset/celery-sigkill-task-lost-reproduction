SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

SIGKILL_OUTPUT_FILENAME := $(shell pwd)/sigkill_output.txt
SIGQUIT_OUTPUT_FILENAME := $(shell pwd)/sigquit_output.txt

install:
	pushd repro/repro && poetry install; popd
.PHONY: install

start-redis:
	docker run --rm -d -p 6379:6379 --name my-redis redis
.PHONY: start-redis


stop-redis:
	docker kill my-redis
.PHONY: stop-redis

start-repro:
	$(MAKE) start-redis
	pushd repro/repro && poetry run python main.py --signal SIGKILL > $(SIGKILL_OUTPUT_FILENAME); popd
	$(MAKE) stop-redis

	$(MAKE) start-redis
	pushd repro/repro && poetry run python main.py --signal SIGQUIT > $(SIGQUIT_OUTPUT_FILENAME); popd
	$(MAKE) stop-redis


	cat $(SIGKILL_OUTPUT_FILENAME)
	cat $(SIGQUIT_OUTPUT_FILENAME)

.PHONY: start-repro

.DEFAULT_GOAL := help
help: Makefile
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n"} /^[\/\.a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
