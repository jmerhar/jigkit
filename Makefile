.PHONY: install test coverage lint build lockfile release check clean

# help, devtools-update and coverage-tooling come from jmerhar/devtools; make fetches them on the
# first run and whenever devtools.toml changes.
.DEFAULT_GOAL := help
include .devtools/make/devtools.mk
.devtools/make/devtools.mk: devtools.toml bin/devtools-fetch.sh
	bin/devtools-fetch.sh

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

lint: ## ruff (lint and format), ShellCheck, the lockfile's registry, one version everywhere
	bin/lint.sh

check: lint coverage ## Everything (gate a commit on this)

##@ Releasing

build: ## Build the Python package into python/dist and check it
	bin/build.sh

lockfile: ## Regenerate js/package-lock.json (Linux binaries, public registry URLs; needs Docker)
	.devtools/bin/lockfile.sh

release: ## Cut a release: make release V=X.Y.Z (commits and tags; pushing publishes)
	.devtools/bin/release.sh $(V)

##@ Housekeeping

clean: ## Remove test, coverage and build output
	rm -rf python/htmlcov python/coverage.json python/coverage.xml python/.coverage* \
		python/junit python/.pytest_cache python/build python/dist .ruff_cache
