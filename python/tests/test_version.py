"""The package reports its own version."""

from importlib.metadata import version

import jigkit


def test_version_matches_the_installed_distribution() -> None:
    assert jigkit.__version__ == version("jigkit")
