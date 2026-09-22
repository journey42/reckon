"""Datetime helpers shared across utils.

DB columns are ``timestamp without time zone`` (naive UTC wall-clock values).
SQLModel 0.0.45 changed its type mapping so plain ``datetime`` fields load as
timezone-aware (``UTCDateTime``), which turns every naive/aware comparison
against ``datetime.utcnow()`` into a TypeError. These helpers normalize either
side so the comparisons keep working no matter which sqlmodel version is
installed (we pin 0.0.38, but a future bump must not silently break auth and
rooms again).
"""

from datetime import datetime, timezone


def naive_utc(dt: datetime | None) -> datetime | None:
    """Coerce a possibly tz-aware datetime to naive UTC wall-clock time."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt