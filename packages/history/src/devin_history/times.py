"""Timestamp helpers — Devin's stores use epoch **milliseconds** (SCHEMA.md).

A tolerance band keeps legacy/second-precision data renderable: any value
>= 1e11 is treated as ms, anything smaller as seconds.
"""

from __future__ import annotations

from datetime import datetime, timezone

_MS_THRESHOLD = 1e11


def to_seconds(ts: float | None) -> float:
    """Normalize an epoch value (s or ms) to seconds."""
    if not ts:
        return 0.0
    ts = float(ts)
    return ts / 1000.0 if ts >= _MS_THRESHOLD else ts


def fmt_ts(ts: float | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Human-readable local time for an epoch s/ms value; "" when unset."""
    if not ts:
        return ""
    return datetime.fromtimestamp(to_seconds(ts), tz=timezone.utc).astimezone().strftime(fmt)


def duration_minutes(start: float | None, end: float | None) -> float:
    """Minutes between two epoch values in the same unit."""
    if not start or not end:
        return 0.0
    unit = 1000.0 if float(start) >= _MS_THRESHOLD or float(end) >= _MS_THRESHOLD else 1.0
    return max(0.0, (float(end) - float(start)) / (60.0 * unit))
