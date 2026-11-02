# Changelog

All notable changes to jigkit are recorded here. The Python and npm packages share one version.

## Unreleased

## 0.3.0 — 2026-11-02

### Added

- `jigkit.web` (extra `web`), building blocks for a FastAPI application:
  - `install_write_guard`: a write under the API needs `X-Requested-With` and the
    application's own Origin;
  - `install_security_headers`: nosniff, a same-origin referrer, no framing;
  - `mount_spa`: the built app with immutable assets, an uncached shell and a 404 for unknown
    API paths;
  - `health_router`: `/health` that queries the database and answers 503 when it cannot;
  - `web_manifest`, `manifest_response` and `preferred_language`: the PWA manifest;
  - `serve`: uvicorn, believing forwarded headers only from `FORWARDED_ALLOW_IPS`.
- `jigkit.scheduler`: `TickLoop`, in-process work on a fixed tick that survives a failing tick.
- `jigkit.notify` (extra `notify`): `AppriseSender`, which sends off the event loop, and
  `redact_url`; `jigkit.testing.notify.RecordingSender` for tests.
- `jigkit.ratelimit`: `RateLimiter`, a token bucket per client with bounded memory.

## 0.2.0 — 2026-11-01

### Added

- `jigkit.sinks`: `Point`, whose timestamp the caller always sets with an explicit `Precision`;
  `Outcome` (OK, RETRY, REJECT); the `Sink` protocol (write, check, flush, close); and
  `dump_points` / `load_points`, the neutral form a backlog waits in.
- `jigkit.spool`: a bounded, durable on-disk queue of batches, with refused batches kept apart
  in `rejected/`. One spool per destination.
- `jigkit.delivery`: write now, or spool and replay oldest first with growing pauses; counts
  each outcome through an application's own `DeliveryEvents`.
- `jigkit.influx` (extra `influx`): line protocol to InfluxDB 3 and 2.x in each batch's own
  precision, the OK / RETRY / REJECT classification of a write, and SQL reads from InfluxDB 3
  with a cached catalogue of tables, tags and fields.
- `jigkit.heartbeat` (extra `heartbeat`): calls a push monitor's URL after delivered writes, at
  most once per interval, logging only its host.
- `jigkit.testing.http`: a real stand-in HTTP server that records every request.

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
