"""Points, their precision, and the neutral text form they wait in while a sink is down."""

from __future__ import annotations

import pytest

from jigkit.sinks import Point, Precision, dump_points, load_points

S = Precision.SECONDS

POINTS = [
    Point(
        "indoor",
        (("name", "Spare room"), ("station", "home")),
        1791500484,
        {"t": 21.0},
        precision=S,
    ),
    Point(
        "battery",
        (("station", "home"),),
        1791500484,
        {"low": False, "model": "WH65 é"},
        precision=S,
    ),
    Point(
        "meter",
        (("device", "a"),),
        1791500484123,
        {"code": 3, "w": 3.0},
        precision=Precision.MILLISECONDS,
    ),
]


def test_points_survive_the_round_trip_with_their_types_and_precision() -> None:
    """60.0 must not come back as 60, nor False as 0: the database fixes a field's type."""
    back = load_points(dump_points(POINTS))

    assert back == POINTS
    assert isinstance(back[0].fields["t"], float)
    assert back[1].fields["low"] is False
    assert type(back[2].fields["code"]) is int
    assert back[2].precision is Precision.MILLISECONDS


def test_no_points_survive_too() -> None:
    assert load_points(dump_points([])) == []


def test_an_entry_without_a_precision_counts_in_seconds() -> None:
    """The four-element form, as spooled before points carried a precision."""
    (point,) = load_points('[["indoor",[["station","home"]],1791500484,{"t":21.0}]]')

    assert point == Point("indoor", (("station", "home"),), 1791500484, {"t": 21.0}, precision=S)


@pytest.mark.parametrize(
    "text",
    [
        "indoor,station=home temp_c=21.0 1791500484",
        "{}",
        "[[1, 2]]",
        '[["t", 3, 1, {}]]',
        '[["t", [], 1, {}, "s", "extra"]]',
        '[["t", [], 1, {}, "fortnights"]]',
    ],
)
def test_anything_else_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="not a list of points"):
        load_points(text)


def test_a_precision_is_required() -> None:
    with pytest.raises(TypeError, match="precision"):
        Point("indoor", (), 1, {"t": 1.0})  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("timestamp", "precision", "wanted", "expected"),
    [
        (1791500484, Precision.SECONDS, Precision.NANOSECONDS, 1791500484_000_000_000),
        (1791500484123, Precision.MILLISECONDS, Precision.MICROSECONDS, 1791500484123_000),
        (1791500484999, Precision.MILLISECONDS, Precision.SECONDS, 1791500484),
        (5, Precision.SECONDS, Precision.SECONDS, 5),
    ],
)
def test_timestamp_in_another_unit(
    timestamp: int, precision: Precision, wanted: Precision, expected: int
) -> None:
    point = Point("t", (), timestamp, {"v": 1.0}, precision=precision)

    assert point.timestamp_in(wanted) == expected
