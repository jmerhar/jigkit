"""AppSettings: blank values, secret files, the time zone and the database URL."""

from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from jigkit.settings import AppSettings


class SecretSettings(AppSettings):
    """Settings with a secret that can come from a file, and a file field with no target."""

    api_key: str | None = None
    api_key_file: Path | None = None
    certificate_file: Path | None = None
    port: int = 8000
    port_file: Path | None = None


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run each test away from any .env file and with none of these variables set."""
    monkeypatch.chdir(tmp_path)
    for name in ("STATIC_DIR", "COOKIE_SECURE", "TZ", "API_KEY", "API_KEY_FILE", "DATA_DIR"):
        monkeypatch.delenv(name, raising=False)


class TestBlankValues:
    def test_a_blank_variable_leaves_its_field_at_the_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Compose passes an unset `${VAR:-}` as an empty string.
        monkeypatch.setenv("STATIC_DIR", "")
        monkeypatch.setenv("COOKIE_SECURE", "  ")

        settings = AppSettings()

        assert settings.static_dir is None
        assert settings.cookie_secure is None

    def test_a_set_variable_is_used(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("STATIC_DIR", "/srv/static")
        monkeypatch.setenv("COOKIE_SECURE", "false")

        settings = AppSettings()

        assert settings.static_dir == Path("/srv/static")
        assert settings.cookie_secure is False

    def test_input_that_is_not_a_mapping_reaches_pydantic_unchanged(self) -> None:
        # Pydantic, not the blank-value filter, reports the wrong shape.
        with pytest.raises(ValidationError, match="valid dictionary"):
            AppSettings.model_validate(["not", "a", "mapping"])


class TestSecretFiles:
    def test_a_secret_is_read_from_its_file_and_stripped(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        secret = tmp_path / "api_key"
        secret.write_text("s3cret\n")
        monkeypatch.setenv("API_KEY_FILE", str(secret))

        assert SecretSettings().api_key == "s3cret"

    def test_a_value_and_a_file_together_are_refused(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        secret = tmp_path / "api_key"
        secret.write_text("from-file")
        monkeypatch.setenv("API_KEY", "direct")
        monkeypatch.setenv("API_KEY_FILE", str(secret))

        with pytest.raises(ValidationError, match="API_KEY and API_KEY_FILE are exclusive"):
            SecretSettings()

    def test_a_blank_value_beside_a_file_is_not_a_conflict(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        secret = tmp_path / "api_key"
        secret.write_text("from-file")
        monkeypatch.setenv("API_KEY", "")
        monkeypatch.setenv("API_KEY_FILE", str(secret))

        assert SecretSettings().api_key == "from-file"

    def test_a_blank_file_variable_means_no_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("API_KEY", "direct")
        monkeypatch.setenv("API_KEY_FILE", "")

        assert SecretSettings().api_key == "direct"

    def test_an_empty_file_is_refused(self, tmp_path: Path) -> None:
        secret = tmp_path / "api_key"
        secret.write_text("  \n")

        with pytest.raises(ValidationError, match="API_KEY_FILE: .* is empty"):
            SecretSettings(api_key_file=secret)

    def test_an_unreadable_file_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="API_KEY_FILE: cannot read"):
            SecretSettings(api_key_file=tmp_path / "missing")

    def test_a_value_from_a_file_takes_its_field_type(self, tmp_path: Path) -> None:
        port = tmp_path / "port"
        port.write_text("9000\n")

        assert SecretSettings(port_file=port).port == 9000

    def test_a_value_from_a_file_that_does_not_fit_its_type_is_refused(
        self, tmp_path: Path
    ) -> None:
        port = tmp_path / "port"
        port.write_text("not-a-number")

        with pytest.raises(ValidationError, match="valid integer"):
            SecretSettings(port_file=port)

    def test_a_file_field_without_a_target_is_left_alone(self, tmp_path: Path) -> None:
        certificate = tmp_path / "cert.pem"

        settings = SecretSettings(certificate_file=certificate)

        assert settings.certificate_file == certificate
        assert settings.api_key is None


class TestTimeZone:
    def test_read_from_tz(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TZ", "Europe/Lisbon")

        settings = AppSettings()

        assert settings.timezone == "Europe/Lisbon"
        assert settings.zone == ZoneInfo("Europe/Lisbon")

    def test_defaults_to_utc(self) -> None:
        assert AppSettings().timezone == "UTC"

    @pytest.mark.parametrize("zone", ["Europe/Atlantis", "../etc/passwd"])
    def test_an_unknown_zone_is_refused(self, zone: str) -> None:
        with pytest.raises(ValidationError, match="unknown time zone"):
            AppSettings(timezone=zone)


class TestDatabaseUrl:
    def test_defaults_to_the_subclass_file_in_the_data_directory(self, tmp_path: Path) -> None:
        class Named(AppSettings):
            database_filename = "named.db"

        settings = Named(data_dir=tmp_path)

        assert settings.resolved_database_url == f"sqlite+aiosqlite:///{tmp_path / 'named.db'}"

    def test_an_explicit_url_wins(self) -> None:
        url = "postgresql+asyncpg://db/app"

        assert AppSettings(database_url=url).resolved_database_url == url
