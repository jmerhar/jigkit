# jigkit

The runtime foundations shared by small self-hosted web apps. One repository, two packages
released under one version: Python `jigkit` in `python/` (published to PyPI) and, later, npm
`@jmerhar/jigkit` in `js/`.

## This repository is public, and its packages are published permanently

Nothing private goes into a commit, a comment, a test fixture, a docstring or a package: no
employer or internal names, hostnames, registries or tooling; no names of private projects; no
personal locations, providers or paths. Examples use generic names (`myapp`, `owners`, `pets`).
A release on PyPI or npm can never be replaced, only yanked.

## Layout

```
python/src/jigkit/
  settings.py      AppSettings: blank = unset, X / X_FILE secrets, TZ, database URL
  db.py            async engine with SQLite pragmas, session factory, session_scope
  models.py        Base (naming convention), UtcDateTime, TimestampMixin
  migrations.py    run_migrations(): the whole of an application's alembic/env.py
  logging.py       configure_logging(), apply_level()
  healthcheck.py   python -m jigkit.healthcheck URL --expect KEY=VALUE
  secrets.py       load_or_create_secret()
  testing/         pytest plugin (data_dir, no_network) and migration checks
python/tests/
  sample_app/      a small application with its own Alembic project, for the migration tests
bin/               every script the Makefile and CI run
```

## Things worth knowing

- **Migrations keep foreign keys off while they run, then run `PRAGMA foreign_key_check`.**
  SQLite's batch mode rebuilds a table by dropping it, and with foreign keys on the drop fires
  every `ON DELETE` rule pointing at it. `tests/test_migrations.py` shows Alembic's stock
  environment losing rows where jigkit's keeps them.
- **The migration checks run Alembic in a subprocess** from the application's directory, as a
  container entrypoint does, with a filtered environment so a developer's own variables cannot
  point them at a real database. Coverage follows them through `patch = ["subprocess"]`.
- **The plugin is loaded from `tests/conftest.py`, not with `-p`,** so coverage is already
  running when it is imported.
- Each module imports only what its extra provides; `import jigkit` imports nothing else.

## Commands

```bash
make install
make check
make test ARGS="tests/test_migrations.py -k rebuild"
```
