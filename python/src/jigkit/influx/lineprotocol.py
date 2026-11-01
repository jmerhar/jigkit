"""Encode points as InfluxDB line protocol, which InfluxDB 3 and 2.x both accept."""

from __future__ import annotations

import math
from collections.abc import Sequence

from jigkit.sinks import FieldValue, Point, Precision


def encode(points: Sequence[Point]) -> tuple[str, Precision]:
    """Encode points as newline-separated line protocol, and the precision to write it at.

    A write states one precision for all its lines. Points that share one are written in it;
    a batch that mixes them is written in the finest it contains, so no timestamp loses
    anything. Points with no field line protocol can carry are left out.
    """
    precisions = {point.precision for point in points}
    precision = max(precisions, key=lambda p: p.per_second) if precisions else Precision.SECONDS
    lines = [line for point in points if (line := encode_point(point, precision))]
    return "\n".join(lines), precision


def encode_point(point: Point, precision: Precision) -> str:
    """Encode one point at ``precision``, or return "" if none of its fields can be written."""
    fields = ",".join(
        f"{_escape_key(name)}={encoded}"
        for name, value in point.fields.items()
        if (encoded := _value(value)) is not None
    )
    if not fields:
        return ""
    # Line protocol forbids an empty tag value, so such a tag is left off rather than written.
    tags = "".join(
        f",{_escape_key(key)}={_escape_key(value)}" for key, value in point.tags if value
    )
    return f"{_escape_measurement(point.table)}{tags} {fields} {point.timestamp_in(precision)}"


def _value(value: FieldValue) -> str | None:
    """Encode a field value, or None for one line protocol cannot represent.

    A float is written as one even when it has no fraction: InfluxDB fixes a field's type on its
    first write, so a humidity first seen as ``60`` would otherwise reject every later ``60.5``.
    An int is written as an integer.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return f"{value}i"
    if isinstance(value, float):
        return repr(value) if math.isfinite(value) else None
    escaped = _flatten(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _flatten(text: str) -> str:
    """Replace line breaks with spaces: line protocol has no escape for them, and one would end
    the line mid-point, making InfluxDB refuse the whole write."""
    return text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def _escape_measurement(name: str) -> str:
    """Escape a measurement name: commas and spaces would end it early."""
    return _flatten(name).replace("\\", "\\\\").replace(",", "\\,").replace(" ", "\\ ")


def _escape_key(name: str) -> str:
    """Escape a tag key, tag value or field key: commas, equals signs and spaces."""
    return (
        _flatten(name)
        .replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace("=", "\\=")
        .replace(" ", "\\ ")
    )
