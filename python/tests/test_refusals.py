"""The refusal codes, the same in the Python and the npm package."""

from __future__ import annotations

from pathlib import Path

from jigkit import refusals


def test_the_codes_match_the_npm_package() -> None:
    api = (Path(__file__).parents[2] / "js" / "src" / "api.ts").read_text(encoding="utf-8")

    assert f'NOT_AUTHENTICATED = "{refusals.NOT_AUTHENTICATED}"' in api
    assert f'SETUP_REQUIRED = "{refusals.SETUP_REQUIRED}"' in api
