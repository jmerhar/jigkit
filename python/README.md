# jigkit

The shared foundations of small self-hosted web apps built on FastAPI, async SQLAlchemy and
Svelte: settings, database, migrations, logging, health checks and test fixtures, each hardened
once instead of copied between applications.

```bash
pip install "jigkit[db]"
```

| Module | Extra | What it gives an application |
|---|---|---|
| `jigkit.settings` | — | `AppSettings`: blank environment values mean unset, `X` or `X_FILE` for secrets (never both), a validated `TZ`, a data directory |
| `jigkit.db` | `db` | an async engine with SQLite's pragmas (foreign keys, WAL, busy timeout), a session factory, a commit-or-roll-back `session_scope` |
| `jigkit.models` | `db` | a declarative `Base` with deterministic constraint names, `UtcDateTime`, `TimestampMixin` |
| `jigkit.migrations` | `db` | the whole of an Alembic `env.py`, with foreign keys off during SQLite table rebuilds and checked afterwards |
| `jigkit.logging` | — | stream and rotating file handlers, a level that changes at runtime, credential-carrying HTTP client loggers kept quiet |
| `jigkit.healthcheck` | — | `python -m jigkit.healthcheck URL --expect database=connected`, a container health probe |
| `jigkit.secrets` | — | `load_or_create_secret`, a generated secret kept owner-only in the data directory |
| `jigkit.sinks` | — | `Point` (timestamp with an explicit precision), `Outcome`, the `Sink` protocol, the neutral spooled form |
| `jigkit.spool`, `jigkit.delivery` | — | a bounded on-disk queue per destination, and write-now-or-spool-and-replay |
| `jigkit.influx` | `influx` | InfluxDB 3 and 2.x sinks: line protocol in each batch's precision, and SQL reads from InfluxDB 3 |
| `jigkit.heartbeat` | `heartbeat` | a push-monitor heartbeat after delivered writes, at most once per interval |
| `jigkit.testing` | `testing` | a pytest plugin (`data_dir`, `no_network`), migration checks run through the application's own `env.py`, and a recording stand-in HTTP server |

PostgreSQL is supported through the `postgres` extra. Python 3.14 or newer.

See the [repository](https://github.com/jmerhar/jigkit) for the changelog and documentation.
