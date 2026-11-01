"""Line protocol encoding."""

from __future__ import annotations

from jigkit.influx.lineprotocol import encode, encode_point
from jigkit.sinks import Point, Precision

S = Precision.SECONDS


def point(
    fields: dict,
    tags: tuple = (("station", "home"),),
    table: str = "indoor",
    *,
    timestamp: int = 1791500484,
    precision: Precision = S,
) -> Point:
    """A point in the indoor table, at second precision unless asked otherwise."""
    return Point(table, tags, timestamp, fields, precision=precision)


def test_a_plain_row() -> None:
    assert (
        encode_point(point({"temp_c": 23.2222}), S)
        == "indoor,station=home temp_c=23.2222 1791500484"
    )


def test_whole_numbers_are_still_written_as_floats() -> None:
    """A field first written as `60` would reject every later `60.5`."""
    assert encode_point(point({"humidity_pct": 60.0}), S).endswith("humidity_pct=60.0 1791500484")


def test_a_code_is_written_as_an_integer() -> None:
    """A code is a category, never fractional, so it keeps the type it has."""
    assert encode_point(point({"weather_code": 61}), S).endswith("weather_code=61i 1791500484")


def test_booleans_and_strings() -> None:
    line = encode_point(point({"low": False, "model": 'HP "Pro" \\ 2'}), S)

    assert "low=false" in line
    assert 'model="HP \\"Pro\\" \\\\ 2"' in line


def test_true_is_true() -> None:
    assert "leak=true" in encode_point(point({"leak": True}), S)


def test_tag_values_and_keys_are_escaped() -> None:
    """A room called `Spare room, east` must not split the tag set."""
    line = encode_point(point({"t": 1.0}, (("name", "Spare room, east=1"), ("station", "home"))), S)

    assert line.startswith("indoor,name=Spare\\ room\\,\\ east\\=1,station=home ")


def test_field_keys_and_measurements_are_escaped() -> None:
    """Keys can come from a source verbatim."""
    line = encode_point(point({"odd key,x=y": 1.0}, table="un mapped,t"), S)

    assert line.startswith("un\\ mapped\\,t,station=home odd\\ key\\,x\\=y=1.0 ")


def test_an_empty_tag_value_is_omitted() -> None:
    """Line protocol forbids it, so the tag is left off rather than breaking the line."""
    line = encode_point(point({"t": 1.0}, (("name", ""), ("station", "home"))), S)

    assert line == "indoor,station=home t=1.0 1791500484"


def test_non_finite_floats_are_skipped() -> None:
    line = encode_point(point({"a": float("nan"), "b": float("inf"), "c": 2.0}), S)

    assert line == "indoor,station=home c=2.0 1791500484"


def test_a_row_with_nothing_writable_is_dropped() -> None:
    assert encode_point(point({"a": float("nan")}), S) == ""
    assert encode([point({"a": float("nan")}), point({"b": 1.0})]) == (
        "indoor,station=home b=1.0 1791500484",
        S,
    )


def test_a_line_break_anywhere_stays_on_one_line() -> None:
    """One newline would split the point, and InfluxDB would refuse the whole write."""
    line = encode_point(
        point(
            {"odd\nkey": 1.0, "note": "first\r\nsecond"},
            (("name", "Living\nroom"), ("station", "home")),
            table="un\nmapped",
        ),
        S,
    )

    assert "\n" not in line and "\r" not in line
    assert line.startswith("un\\ mapped,name=Living\\ room,station=home ")
    assert 'note="first second"' in line


def test_a_batch_in_one_precision_is_written_in_it() -> None:
    ms = Precision.MILLISECONDS
    text, precision = encode([point({"w": 1.0}, timestamp=1791500484123, precision=ms)])

    assert (text, precision) == ("indoor,station=home w=1.0 1791500484123", ms)


def test_a_mixed_batch_is_written_in_the_finest_precision_it_holds() -> None:
    text, precision = encode(
        [
            point({"a": 1.0}),
            point({"b": 2.0}, timestamp=1791500484123456, precision=Precision.MICROSECONDS),
        ]
    )

    assert precision is Precision.MICROSECONDS
    assert text.splitlines() == [
        "indoor,station=home a=1.0 1791500484000000",
        "indoor,station=home b=2.0 1791500484123456",
    ]


def test_an_empty_batch_encodes_to_nothing() -> None:
    assert encode([]) == ("", S)
