# jigkit

[![CI](https://github.com/jmerhar/jigkit/actions/workflows/ci.yml/badge.svg)](https://github.com/jmerhar/jigkit/actions/workflows/ci.yml)

The shared foundations of small self-hosted web apps built on FastAPI, async SQLAlchemy and
Svelte. Every such app needs the same parts — settings read from the environment, a database
with migrations, logging, a health probe, test fixtures — and copying them from one app to the
next lets each copy drift and keep bugs the others have fixed. jigkit is those parts, written
once and tested once.

**Status:** pre-release (0.x). The API changes between minor versions until 1.0.

## Packages

| Directory | Package | Contents |
|---|---|---|
| [`python/`](python/) | `jigkit` (PyPI) | settings, database, migrations, logging, health probe, secrets, sinks with a durable spool, InfluxDB, a push-monitor heartbeat, pytest plugin |

A matching npm package with the frontend helpers (theme, i18n, API client) is planned and will be
released under the same version.

## Using it

```bash
pip install "jigkit[db]"
```

```python
from pathlib import Path

from jigkit.settings import AppSettings


class Settings(AppSettings):
    database_filename = "myapp.db"
    api_key: str | None = None
    api_key_file: Path | None = None  # API_KEY or API_KEY_FILE, never both
```

An application's `alembic/env.py` is three lines:

```python
from jigkit.migrations import run_migrations
from myapp.config import Settings
from myapp.models import Base

run_migrations(Settings().resolved_database_url, Base.metadata)
```

and its container health check needs no code at all:

```dockerfile
HEALTHCHECK CMD ["python", "-m", "jigkit.healthcheck", \
                 "http://127.0.0.1:8000/api/health", "--expect", "database=connected"]
```

Its tests get fixtures, and migration checks that run through the application's real `env.py`:

```python
# conftest.py
pytest_plugins = ["jigkit.testing"]

# test_migrations.py
from jigkit.testing.migrations import MigrationProject

PROJECT = MigrationProject(Path(__file__).parents[1], database_filename="myapp.db")


def test_models_match_migrations(data_dir):
    PROJECT.assert_models_match(Base.metadata, data_dir)


def test_one_head():
    PROJECT.assert_single_head()


def test_rebuilding_a_table_keeps_the_rows_pointing_at_it(data_dir, tmp_path):
    PROJECT.assert_parent_rebuilds_keep_children(Base.metadata, data_dir, tmp_path)
```

See [`python/README.md`](python/README.md) for the module list.

## Developing

```bash
make install   # virtualenv with the package and its checks
make check     # ruff, ShellCheck, the suite and the coverage gate
make test ARGS="tests/test_settings.py -k blank"
```

Python 3.14 or newer.

## License

MIT
