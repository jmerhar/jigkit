# jigkit

The runtime foundations shared by small self-hosted web apps. One repository, two packages
released under one version: Python `jigkit` in `python/` (published to PyPI) and npm
`@jmerhar/jigkit` in `js/`.

## This repository is public, and its packages are published permanently

Nothing private goes into a commit, a comment, a test fixture, a docstring or a package: no
employer or internal names, hostnames, registries or tooling; no names of private projects; no
personal locations, providers or paths. Examples use generic names (`myapp`, `owners`, `pets`).
A release on PyPI or npm can never be replaced, only yanked.

## Writing for readers of this repository

Commit messages, comments, docstrings, READMEs, the changelog and test comments must make sense
to someone who has only this repository. Describe jigkit in its own terms: what the code does
and the standing reason why. Never lean on what such a reader cannot see: particular
deployments or hosts, the applications that use jigkit or the code it was taken from, systems
something replaced, other sessions or "the brief", "in production", or where a test's expected
value came from. Name another project only by linking its public repository.

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
  sinks.py         Point (timestamp + explicit precision), Outcome, Sink, dump/load_points
  spool.py         bounded on-disk queue of batches; one per destination
  delivery.py      write now, or spool and replay oldest first; DeliveryEvents
  influx/          InfluxDB 3 and 2.x sinks, line protocol, SQL reads (extra influx)
  heartbeat.py     push-monitor heartbeat after delivered writes (extra heartbeat)
  web/             FastAPI building blocks: access.py (AccessPolicy), guard.py, spa.py, health.py,
                   manifest.py, server.py (serve) (extra web)
  scheduler.py     TickLoop
  notify.py        AppriseSender, redact_url (extra notify)
  ratelimit.py     RateLimiter
  auth/            passwords.py, throttle.py, cookies.py (extra auth); sessions.py
                   (SessionMixin, SessionStore; extras auth and db); passkeys.py (extras
                   passkeys and db)
  testing/         pytest plugin (data_dir, no_network), migration checks, stand-in HTTP server,
                   RecordingSender, SoftAuthenticator (passkeys.py)
python/tests/
  sample_app/      a small application with its own Alembic project, for the migration tests
js/src/            the npm package: storage.ts, theme.ts, i18n/ (index, build, testing), api.ts,
                   format.ts, passkeys.ts; one subpath export each
js/tests/          Vitest, in jsdom
bin/               every script the Makefile and CI run
tooling/           tests of the scripts in bin/ (not part of the package)
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
- **A point's timestamp always comes from its source, with its precision.** A write is sent in
  the batch's own precision, or the finest one in a mixed batch; nothing is left for the server
  to stamp on arrival, which would record when a backlog was replayed.
- **`load_points` also reads the four-element form, in seconds**, which spools written before
  points carried a precision still hold.
- **Session cookies never read X-Forwarded-Proto themselves.** The Secure flag follows the
  request's scheme, which uvicorn sets from a proxy it believes (`FORWARDED_ALLOW_IPS`); reading
  the header directly would let any client choose it.
- **The web pieces are building blocks, not a framework.** An application keeps its own app
  factory and lifespan, and applies what it wants; `mount_spa` goes last because its catch-all
  answers whatever no route matched.
- Each module imports only what its extra provides; `import jigkit` imports nothing else.

## Commands

```bash
make install
make check
make test ARGS="tests/test_migrations.py -k rebuild"
make build                 # sdist and wheel into python/dist, checked with twine
make release V=X.Y.Z       # commit and tag; `git push origin main vX.Y.Z` publishes
```

## Releasing

`bin/release.sh` writes the version into every manifest, dates the changelog's Unreleased
section, commits and tags. Pushing the tag runs `.github/workflows/release.yml`: it tests,
builds, publishes to PyPI by trusted publishing (environment `pypi`, no token), and creates the
GitHub release from the changelog. Between releases the manifest carries the next development
version (`0.2.0.dev0`). `bin/version.py` is tested in `tooling/`.
