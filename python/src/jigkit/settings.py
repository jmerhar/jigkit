"""Settings read from the environment, with the behaviour every application needs.

An application subclasses :class:`AppSettings`, adds its own fields, and gets:

- **Blank means unset.** Compose writes ``VAR: ${VAR:-}`` for an optional setting, so a variable
  nobody set arrives as an empty string. A blank value is dropped before validation, so the
  field takes its default: an empty ``STATIC_DIR`` stays ``None`` instead of becoming
  ``Path(".")``, and an empty ``COOKIE_SECURE`` stays "follow the scheme" instead of failing to
  parse.
- **Secrets from files.** A field ``x`` with a sibling ``x_file`` can be given either directly
  or as a path to a file holding it, such as a mounted Docker secret. Setting both is an error,
  as is a file that is empty or unreadable: either way the application would otherwise run with
  a value nobody intended.
- **A known time zone.** ``TZ`` is validated at startup, so a typo stops the application instead
  of surfacing later as a scheduler that cannot compute the next run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AliasChoices, Field, TypeAdapter, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: The suffix that marks a field as the file form of another.
FILE_SUFFIX = "_file"


class AppSettings(BaseSettings):
    """The settings every application shares.

    Subclass it and add fields. Set ``database_filename`` on the subclass to name the SQLite file
    the default database URL points at.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    #: The SQLite file inside ``data_dir`` that :attr:`resolved_database_url` defaults to.
    database_filename: ClassVar[str] = "app.db"

    #: Where all mutable state lives: the database, generated keys, logs, uploads. One directory
    #: means a deployment has exactly one thing to persist and back up.
    data_dir: Path = Path("data")
    #: Where the built single-page app is served from. Unset, the API runs on its own, which is
    #: how a development stack works (the frontend's dev server serves the app and proxies the API).
    static_dir: Path | None = None
    #: Overrides the default SQLite database in ``data_dir``.
    database_url: str | None = None

    log_level: str = "INFO"

    #: The address people open the application at, behind its reverse proxy.
    public_url: str | None = None
    #: Forces the session cookie's Secure flag on or off. Unset, it follows the request's scheme.
    cookie_secure: bool | None = None
    #: The proxies whose X-Forwarded-For and X-Forwarded-Proto are believed, as uvicorn's
    #: ``forwarded_allow_ips`` takes them. Never ``*``: uvicorn then believes the leftmost
    #: address, which the client wrote itself.
    forwarded_allow_ips: str = "127.0.0.1"

    #: The application's time zone, read from ``TZ``, which the container's clock follows too.
    timezone: str = Field("UTC", validation_alias=AliasChoices("TZ", "timezone"))

    #: The commit the image was built from; unset outside an image.
    revision: str | None = None

    #: Whether in-process scheduled work runs. Tests turn it off and drive the work themselves.
    scheduler_enabled: bool = True
    scheduler_tick_seconds: int = Field(60, ge=1)

    @model_validator(mode="before")
    @classmethod
    def _blank_means_unset(cls, data: Any) -> Any:
        """Drop blank string values, so their fields take their defaults."""
        if not isinstance(data, dict):
            return data
        return {
            key: value
            for key, value in data.items()
            if not (isinstance(value, str) and not value.strip())
        }

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, value: str) -> str:
        """Reject a time zone the standard library does not know."""
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"unknown time zone {value!r}") from error
        return value

    @model_validator(mode="after")
    def _read_secret_files(self) -> Self:
        """Fill each field whose ``*_file`` companion names a file, from that file.

        The file's stripped text is validated as the target field's type, so a number or a flag
        can come from a file as well as a string. The value and its file are exclusive, and the
        file must hold something: an unreadable or empty file is an error rather than a silent
        fall back to the default.
        """
        fields = type(self).model_fields
        for name in fields:
            if not name.endswith(FILE_SUFFIX):
                continue
            target = name.removesuffix(FILE_SUFFIX)
            path = getattr(self, name)
            if target not in fields or path is None:
                continue
            env_target = target.upper()
            if target in self.model_fields_set:
                raise ValueError(
                    f"{env_target} and {env_target}{FILE_SUFFIX.upper()} are exclusive; "
                    "set one of them"
                )
            try:
                value = Path(path).read_text(encoding="utf-8").strip()
            except OSError as error:
                raise ValueError(
                    f"{env_target}{FILE_SUFFIX.upper()}: cannot read {path}: {error.strerror}"
                ) from error
            if not value:
                raise ValueError(f"{env_target}{FILE_SUFFIX.upper()}: {path} is empty")
            setattr(self, target, TypeAdapter(fields[target].annotation).validate_python(value))
        return self

    @property
    def resolved_database_url(self) -> str:
        """The database URL, defaulting to a SQLite file inside the data directory."""
        if self.database_url:
            return self.database_url
        return f"sqlite+aiosqlite:///{self.data_dir / self.database_filename}"

    @property
    def zone(self) -> ZoneInfo:
        """The application's time zone."""
        return ZoneInfo(self.timezone)
