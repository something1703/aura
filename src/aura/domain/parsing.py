"""Human-friendly value parsing shared by domain models and the normalizer.

These helpers implement the unit-normalization examples from
docs/IMPLEMENTATION_PHASES.md: ``5m`` -> 300 seconds, ``99.99%`` -> 99.99,
``$15k`` -> 15000.0 USD/month. They are intentionally permissive on input and
strict on output: anything that cannot be parsed unambiguously raises
``ValueError`` so Pydantic can surface a clear validation error.
"""

from __future__ import annotations

import re

_PERCENT_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*%?\s*$")
_CURRENCY_RE = re.compile(
    r"^\s*\$?\s*(-?\d[\d,]*(?:\.\d+)?)\s*([kKmM]?)\s*$"
)
_DURATION_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*([a-zA-Z]*)\s*$")

_DURATION_UNIT_SECONDS = {
    "": None,  # unit-less: caller supplies the assumed unit
    "s": 1,
    "sec": 1,
    "secs": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "mins": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hrs": 3600,
    "hour": 3600,
    "hours": 3600,
}

_CURRENCY_MULTIPLIERS = {"": 1, "k": 1_000, "m": 1_000_000}


def parse_percentage(value: object) -> float:
    """Parse a percentage-like value (``99.99``, ``"99.99%"``) into a float 0-100."""

    if isinstance(value, bool):
        raise ValueError(f"invalid percentage value: {value!r}")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = _PERCENT_RE.match(value)
        if match:
            return float(match.group(1))
    raise ValueError(f"invalid percentage value: {value!r}")


def parse_currency_usd(value: object) -> float:
    """Parse a currency-like value (``15000``, ``"$15k"``, ``"$15,000"``) into USD."""

    if isinstance(value, bool):
        raise ValueError(f"invalid currency value: {value!r}")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = _CURRENCY_RE.match(value)
        if match:
            amount = float(match.group(1).replace(",", ""))
            multiplier = _CURRENCY_MULTIPLIERS[match.group(2).lower()]
            return amount * multiplier
    raise ValueError(f"invalid currency value: {value!r}")


def parse_duration_seconds(value: object, *, assumed_unit_seconds: int = 60) -> float:
    """Parse a duration into seconds.

    Bare numbers are interpreted using ``assumed_unit_seconds`` (default: the
    value is already in minutes, matching fields like ``rto_minutes``).
    Strings may carry an explicit unit suffix such as ``"5m"``, ``"300s"``,
    or ``"1h"``.
    """

    if isinstance(value, bool):
        raise ValueError(f"invalid duration value: {value!r}")
    if isinstance(value, (int, float)):
        return float(value) * assumed_unit_seconds
    if isinstance(value, str):
        match = _DURATION_RE.match(value)
        if match:
            amount = float(match.group(1))
            unit = match.group(2).lower()
            if unit in _DURATION_UNIT_SECONDS:
                unit_seconds = _DURATION_UNIT_SECONDS[unit]
                if unit_seconds is None:
                    unit_seconds = assumed_unit_seconds
                return amount * unit_seconds
    raise ValueError(f"invalid duration value: {value!r}")
