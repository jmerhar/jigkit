"""InfluxDB sinks (extra ``influx``): line protocol over HTTP to InfluxDB 3 and 2.x.

:class:`Influx3Sink` also reads back, with SQL whose table and field names are checked against
the database's own catalogue.
"""

from jigkit.influx.lineprotocol import encode
from jigkit.influx.sink import (
    Influx2Sink,
    Influx3Sink,
    InfluxSink,
    QueryError,
    TableInfo,
    TableNotFound,
    classify,
    parse_time,
    sql_timestamp,
)

__all__ = [
    "Influx2Sink",
    "Influx3Sink",
    "InfluxSink",
    "QueryError",
    "TableInfo",
    "TableNotFound",
    "classify",
    "encode",
    "parse_time",
    "sql_timestamp",
]
