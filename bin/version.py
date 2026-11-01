#!/usr/bin/env python3
"""The release version, which every package's manifest and CHANGELOG.md carry.

    version.py check [TAG]   every manifest names the same version; with a tag (v1.2.3), that the
                             manifests name that version and CHANGELOG.md has its dated section
    version.py set X.Y.Z     write X.Y.Z, which must follow the current version, into every
                             manifest and date CHANGELOG.md's Unreleased section as X.Y.Z's; a
                             release that cannot be cut changes nothing
    version.py notes X.Y.Z   print X.Y.Z's section of CHANGELOG.md, without its heading

The Python and npm packages share one version, so a release names it in each manifest at once.
`--root DIR` reads and writes a checkout other than this one, as the tests do.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

CHANGELOG = "CHANGELOG.md"
#: Each manifest and the pattern of its own version line.
MANIFESTS = {
    "python/pyproject.toml": re.compile(r'(?m)^(version = ")([^"]*)(")$'),
}
#: A release version. Between releases a manifest may carry a development version after it
#: (0.2.0.dev0), which counts as coming before the release it names.
RELEASE = re.compile(r"\d+\.\d+\.\d+")
DEVELOPMENT = re.compile(r"(\d+\.\d+\.\d+)\.dev\d+")
UNRELEASED = "## Unreleased"
UNRELEASED_HEADING = re.compile(r"(?m)^## Unreleased$")


class VersionError(Exception):
    """What stops a check or a release, said to the person running it."""


def _read(root: Path, path: str) -> str:
    try:
        return (root / path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise VersionError(f"{path} is missing") from None


def versions(root: Path) -> dict[str, str]:
    """Every manifest's version, by manifest."""
    found = {}
    for path, pattern in MANIFESTS.items():
        match = pattern.search(_read(root, path))
        if match is None:
            raise VersionError(f"{path} names no version where one is expected")
        found[path] = match.group(2)
    return found


def _order(version: str) -> tuple[int, int, int, int]:
    """A key that sorts versions, a development version just before the release it names."""
    if RELEASE.fullmatch(version):
        return (*map(int, version.split(".")), 1)  # type: ignore[return-value]
    development = DEVELOPMENT.fullmatch(version)
    if development:
        return (*map(int, development.group(1).split(".")), 0)  # type: ignore[return-value]
    raise VersionError(f"{version} is neither a release like 1.2.3 nor a development version")


def check(root: Path, tag: str | None) -> str:
    """The version every manifest agrees on; with `tag`, also that it is the tag's, released."""
    found = versions(root)
    if len(set(found.values())) != 1:
        listed = "\n".join(f"  {where}: {v}" for where, v in found.items())
        raise VersionError(f"the manifests name different versions:\n{listed}")
    version = next(iter(found.values()))
    if tag is not None:
        if tag != f"v{version}":
            raise VersionError(f"the tag is {tag}, but the manifests name {version}")
        notes(root, version)
    return version


def set_version(root: Path, version: str, today: date) -> None:
    """Write `version` into every manifest and date the Unreleased changelog section as it.

    Every file is worked out before any is written, so a release that cannot be cut changes
    nothing.
    """
    if not RELEASE.fullmatch(version):
        raise VersionError(f"{version} is not a version like 1.2.3")
    current = check(root, None)
    if _order(version) <= _order(current):
        raise VersionError(f"{version} is not after {current}, the current version")
    text = _read(root, CHANGELOG)
    headings = UNRELEASED_HEADING.findall(text)
    if len(headings) != 1:
        found = "no" if not headings else "more than one"
        raise VersionError(f"{CHANGELOG} has {found} '{UNRELEASED}' section to release")
    if not any(
        line.strip() and not line.startswith("#")
        for line in _section(text, UNRELEASED).splitlines()
    ):
        raise VersionError(f"{CHANGELOG}'s '{UNRELEASED}' section is empty")
    if re.search(rf"(?m)^## {re.escape(version)}(\s|$)", text):
        raise VersionError(f"{CHANGELOG} already has a section for {version}")
    planned = {CHANGELOG: UNRELEASED_HEADING.sub(f"## {version} — {today.isoformat()}", text, 1)}
    # check() above found every manifest's version line, so each substitution has its line.
    for path, pattern in MANIFESTS.items():
        planned[path] = pattern.sub(rf"\g<1>{version}\g<3>", _read(root, path), count=1)
    for path, content in planned.items():
        (root / path).write_text(content, encoding="utf-8")
    check(root, f"v{version}")


def notes(root: Path, version: str) -> str:
    """`version`'s changelog section, without its heading."""
    text = _read(root, CHANGELOG)
    match = re.search(rf"(?m)^## {re.escape(version)} — \d{{4}}-\d{{2}}-\d{{2}}$", text)
    if match is None:
        raise VersionError(f"{CHANGELOG} has no dated section for {version}")
    return _section(text, match.group(0)).strip() + "\n"


def _section(text: str, heading: str) -> str:
    """The text under `heading`, up to the next section's."""
    after = text.split(heading + "\n", 1)[1] if heading + "\n" in text else ""
    return re.split(r"(?m)^## ", after, maxsplit=1)[0]


def main(argv: list[str] | None = None) -> int:
    """Run one command; a VersionError is reported and exits 1."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check").add_argument("tag", nargs="?")
    commands.add_parser("set").add_argument("version")
    commands.add_parser("notes").add_argument("version")
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            print(f"every manifest names {check(args.root, args.tag)}")
        elif args.command == "set":
            set_version(args.root, args.version, date.today())
        else:
            sys.stdout.write(notes(args.root, args.version))
    except VersionError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
