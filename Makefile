.DEFAULT_GOAL := help
.PHONY: help install test test-tooling coverage lint build release check clean

##@ Setup

install: ## Create the virtualenv and install the package with everything its checks need
	python3.14 -m venv python/.venv
	python/.venv/bin/pip install --quiet --upgrade pip
	python/.venv/bin/pip install --quiet -e "python[dev,postgres]"

##@ Checks

test: ## Run the test suite (ARGS pass through to pytest)
	bin/test.sh $(ARGS)

coverage: ## Run the suite with coverage and print the summary CI gates on
	bin/coverage.sh --format md

test-tooling: ## Run the tests of the scripts in bin/
	bin/test-tooling.sh

lint: ## ruff (lint and format) and ShellCheck
	bin/lint.sh

check: lint test-tooling coverage ## Everything (gate a commit on this)

##@ Releasing

build: ## Build the Python package into python/dist and check it
	bin/build.sh

release: ## Cut a release: make release V=X.Y.Z (commits and tags; pushing publishes)
	bin/release.sh $(V)

##@ Housekeeping

clean: ## Remove test, coverage and build output
	rm -rf python/htmlcov python/coverage.json python/coverage.xml python/.coverage* \
		python/junit python/.pytest_cache python/build python/dist .ruff_cache .coverage-report.py

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^##@/ {printf "\n%s\n", substr($$0, 5)} \
		/^[a-z-]+:.*##/ {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
