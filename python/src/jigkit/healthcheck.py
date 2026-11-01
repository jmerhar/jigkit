"""A container health probe: ``python -m jigkit.healthcheck URL [--expect KEY=VALUE ...]``.

Exits 0 only when the URL answers 200 with a JSON object holding every expected value. A probe
that only checked the port would call a container healthy while every request it served failed,
so an application reports what it depends on (``{"database": "connected"}``) and the probe
checks it::

    HEALTHCHECK CMD ["python", "-m", "jigkit.healthcheck",
                     "http://127.0.0.1:8000/api/health", "--expect", "database=connected"]

Only the standard library is used, so the probe starts quickly and needs no extra.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence

TIMEOUT_SECONDS = 5.0


def probe(
    url: str, expect: Mapping[str, object] | None = None, timeout: float = TIMEOUT_SECONDS
) -> int:
    """Report whether the application at ``url`` is healthy, as an exit status.

    Each reason for an unhealthy result is printed to stderr, where Docker keeps it in the
    container's health log.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            # urlopen raises for 4xx and 5xx, so this catches a 2xx that is not 200, which is not
            # an answer to a health question either.
            if response.status != 200:
                return _unhealthy(f"HTTP {response.status}")
            body = json.load(response)
    except urllib.error.HTTPError as error:
        # Closed explicitly: an HTTPError carries the response it was raised from.
        with error:
            return _unhealthy(f"HTTP {error.code}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        return _unhealthy(str(error))

    if not isinstance(body, dict):
        return _unhealthy(f"expected a JSON object, got {type(body).__name__}")
    for key, wanted in (expect or {}).items():
        if body.get(key) != wanted:
            return _unhealthy(f"{key} is {body.get(key)!r}, expected {wanted!r}")
    return 0


def _unhealthy(reason: str) -> int:
    """Print why the probe failed, and return the failing exit status."""
    print(f"unhealthy: {reason}", file=sys.stderr)
    return 1


def _expectation(text: str) -> tuple[str, object]:
    """Parse ``KEY=VALUE``, VALUE as JSON if it parses (``true``, ``3``) and as text if not."""
    key, separator, raw = text.partition("=")
    if not separator or not key:
        raise argparse.ArgumentTypeError(f"expected KEY=VALUE, got {text!r}")
    try:
        value: object = json.loads(raw)
    except json.JSONDecodeError:
        value = raw
    return key, value


def main(argv: Sequence[str] | None = None) -> int:
    """Run the probe from the command line."""
    parser = argparse.ArgumentParser(prog="python -m jigkit.healthcheck", description=__doc__)
    parser.add_argument("url", help="the health endpoint to query")
    parser.add_argument(
        "--expect",
        action="append",
        type=_expectation,
        default=[],
        metavar="KEY=VALUE",
        help="a value the JSON body must hold; repeatable",
    )
    parser.add_argument("--timeout", type=float, default=TIMEOUT_SECONDS)
    arguments = parser.parse_args(argv)
    return probe(arguments.url, dict(arguments.expect), arguments.timeout)


if __name__ == "__main__":
    sys.exit(main())
