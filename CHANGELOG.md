# Changelog

All notable changes to jigkit are recorded here. The Python and npm packages share one version.

## Unreleased

## 0.1.0 — 2026-11-01

### Added

- `jigkit.settings`: `AppSettings`, with blank environment values treated as unset, `X` or
  `X_FILE` for secrets (setting both is an error), a validated `TZ`, and a default SQLite URL in
  the data directory. `tzdata` is a dependency, so `TZ` validates in images without system
  zone data.
- `jigkit.logging`: stream and rotating file handlers, runtime level changes, and HTTP client
  loggers held at WARNING so request URLs and headers are not logged.
- `jigkit.healthcheck`: a container health probe, `python -m jigkit.healthcheck URL --expect
  KEY=VALUE`.
- `jigkit.secrets`: `load_or_create_secret`, created atomically with owner-only permissions.
- `jigkit.db` and `jigkit.models` (extra `db`): an async engine with SQLite's pragmas, a
  commit-or-roll-back `session_scope`, a declarative `Base` with deterministic constraint names,
  `UtcDateTime` and `TimestampMixin`.
- `jigkit.testing` (extra `testing`): a pytest plugin with `data_dir` and `no_network`.
- `jigkit.migrations` and `jigkit.testing.migrations`: an Alembic environment that keeps foreign
  keys off while SQLite rebuilds a table, and checks that run an application's migrations in a
  subprocess — models against migrations, a single head, and rebuilding every referenced table
  without losing the rows pointing at it.
