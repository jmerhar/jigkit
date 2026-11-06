# Changelog

All notable changes to jigkit are recorded here. The Python and npm packages share one version.

## Unreleased

### Fixed

- The base stylesheet draws a drop-down menu's arrow as a chevron that points down while closed
  and up while open; its two halves were drawn on the wrong sides. A select's arrow is the same
  chevron, in each theme's muted colour.

### Changed

- The template imports the base stylesheet in place of its own copy, and its header folds
  behind a menu button on a narrow screen.

## 0.11.0 — 2026-11-06

### Added

- `@jmerhar/jigkit/styles/base.css`, a base stylesheet an application imports before its own
  rules: the colours as custom properties (light, and dark for the device or a chosen theme),
  form controls (a select's arrow is drawn clear of its edge rather than the native one, and
  checkboxes, colour and file inputs are sized to match), buttons (`secondary`, `danger`,
  `link`, `small`), cards, `grid` tables with a scroll container, alerts, tags, chips, tabs,
  figures at a glance (`kpis`), and a header whose navigation, with drop-down groups
  (`nav-menu`), folds behind a menu button on a narrow screen. The class names are the ones the
  Svelte login components carry.

### Fixed

- An application rendered from the template with a long description passes its own lint: the
  description is no longer written into Python source, and the API's summary is read from the
  package metadata pyproject.toml sets. The template check renders with a long description.

## 0.10.0 — 2026-11-02

### Added

- A copier template for a new application on jigkit and devtools (`copier copy gh:jmerhar/jigkit
  myapp`): a FastAPI backend and a Svelte interface with password and passkey
  logins, first-run setup, revocable sessions, English and European Portuguese, Apprise
  notifications and a notes table, with migrations, tests at full coverage, a Dockerfile,
  compose files and a CI workflow. It pins the release it is rendered from. CI renders it and
  runs the new application's own checks, on the current jigkit, up to a running image.

## 0.9.0 — 2026-11-02

### Added

- `@jmerhar/jigkit/auth/svelte`: Svelte 5 components for logging in, which take the
  application's words and API calls as props and carry class names for its stylesheet:
  `LoginForm` (a password, a passkey from a button or from the login field's autofill, offered
  first on a browser that has used one), `SetupForm` (the first account, after fields of the
  application's own), `PasskeyOffer` (setting a passkey up in one tap after a password login)
  and `PasskeyList` (an account's passkeys, added and removed). Svelte is an optional peer
  dependency.
- `passkeyMemory` in `@jmerhar/jigkit/passkeys`: whether a passkey was used on this browser and
  whether the offer to set one up was turned down, under an application's prefix.

### Changed

- The npm package is built with `svelte-package`, and type-checked with `svelte-check`.

## 0.8.2 — 2026-11-02

### Fixed

- The release workflow publishes the npm package from its packed file by path. 0.8.1 reached
  PyPI only as well; `@jmerhar/jigkit` starts at 0.8.2.

## 0.8.1 — 2026-11-02

### Fixed

- The release workflow creates the directory it packs the npm package into, so the npm package
  is published with each release. 0.8.0 reached PyPI only; `@jmerhar/jigkit` starts at 0.8.1,
  identical to the Python package's 0.8.0 apart from the version.

## 0.8.0 — 2026-11-02

### Added

- `@jmerhar/jigkit`, the npm package, with one entry point per module:
  - `storage`: local storage that never throws;
  - `theme`: `applyTheme`, `chosenTheme`, `chooseTheme`;
  - `i18n`: `createLanguage` over an application's Paraglide runtime, and `match`;
  - `i18n/build`: `paraglideOptions`;
  - `i18n/testing`: `catalogueProblems`, which reads messages with variants and can let a
    translation leave placeholders out, `placeholders` and `texts`;
  - `api`: `ApiClient`, `ApiError`, `writeHeader`;
  - `format`: euros, `parseAmount`, percentages in basis points, days, moments,
    `calendarDate`, `whichDay`, `zoneCity`, `fileSize`;
  - `passkeys`: `browserAuthenticator`, `dismissed`, `deviceName`.

## 0.7.0 — 2026-11-02

### Added

- `jigkit.web.AccessPolicy`: a fail-closed access policy, mounted once as a global dependency.
  Every route needs a credential (an application's own check, sync or async) unless it is
  declared open by method and full path template; `route_templates(app)` and
  `AccessPolicy.unknown(app)` let a test hold the declarations to the real route table.
- `jigkit.auth.passkeys` (extras `passkeys` and `db`): the WebAuthn ceremonies that add a
  passkey (`registration_options`, `verify_registration`) and log in with one
  (`authentication_options`, `parse_login`, `verify_login`), with every bad answer raised as
  `PasskeyRejected`; `relying_party` from the public URL or the request; `Ceremonies`, the
  challenges waiting for their answer, bounded and expiring; `hold_ceremony` and
  `clear_ceremony` for the cookie carrying a ceremony's key; and `PasskeyMixin` for an
  application's passkey table.
- `jigkit.testing.passkeys.SoftAuthenticator`: a software authenticator with real ES256 keys,
  for testing passkey routes end to end.

## 0.6.0 — 2026-11-02

### Removed

- `jigkit.auth`'s first-run setup token helpers (`resolve_setup_token`, `setup_token_matches`,
  `SETUP_TOKEN_DISABLED`). Applications built on jigkit do not guard first-run setup with a
  token; a lock against two simultaneous setups is the application's own.

## 0.5.1 — 2026-11-02

### Fixed

- The `web` extra accepts any FastAPI from 0.141 below 1.0, rather than below 0.144, so an
  application can move to a newer FastAPI without waiting for jigkit. The suite passes on
  FastAPI 0.162 with Starlette 1.10.

## 0.5.0 — 2026-11-02

### Added

- `jigkit.auth` (extra `auth`):
  - `hash_password` and `verify_password` (Argon2id with a length floor), and
    `burn_password_check`, so a login naming nobody takes as long as a wrong password;
  - `LoginThrottle`: failed logins per address in a sliding minute, forgotten on success, with
    bounded memory;
  - `resolve_setup_token` and `setup_token_matches`: a generated first-run token, `off` to
    disable it, and a constant-time comparison;
  - `issue_session_cookie`, `clear_session_cookie` and `cookie_secure`: an HttpOnly, SameSite=Lax
    cookie whose Secure flag follows the request's own scheme, never a raw forwarded header.
- `jigkit.auth.sessions` (extras `auth` and `db`): `SessionMixin` for an application's session
  table, and `SessionStore`, which keeps hashed tokens with a sliding expiry and opens, finds,
  ends and prunes them.

## 0.4.0 — 2026-11-02

### Added

- `MigrationProject.assert_parent_rebuilds_keep_children` takes `extra_rows`: further rows for a
  table, each a synthetic row with the given values on top, for a constraint one row per table
  cannot meet (a settlement between two different households, an attachment owned by exactly one
  of two parents). `overrides` can then point a column at one of them.

## 0.3.1 — 2026-11-02

### Fixed

- `jigkit.logging` holds `httpx2` and `httpcore2` at WARNING too, beside `httpx` and
  `httpcore`. jigkit's InfluxDB sinks and heartbeat use httpx2, which logs every request's URL
  at INFO under its own name, so at INFO a push monitor's token reached the log.

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
