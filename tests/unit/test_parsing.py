from __future__ import annotations

import pytest

from aura.domain.parsing import parse_currency_usd, parse_duration_seconds, parse_percentage


@pytest.mark.parametrize(
    "value,expected",
    [
        (99.99, 99.99),
        ("99.99%", 99.99),
        ("99.99", 99.99),
        (100, 100.0),
    ],
)
def test_parse_percentage(value, expected):
    assert parse_percentage(value) == expected


@pytest.mark.parametrize("value", ["not-a-percent", None, "%", True])
def test_parse_percentage_rejects_invalid(value):
    with pytest.raises(ValueError):
        parse_percentage(value)


@pytest.mark.parametrize(
    "value,expected",
    [
        (15000, 15000.0),
        ("15000", 15000.0),
        ("$15k", 15000.0),
        ("$15,000", 15000.0),
        ("15K", 15000.0),
        ("1.5m", 1_500_000.0),
    ],
)
def test_parse_currency_usd(value, expected):
    assert parse_currency_usd(value) == expected


@pytest.mark.parametrize("value", ["free", None, "$", True])
def test_parse_currency_rejects_invalid(value):
    with pytest.raises(ValueError):
        parse_currency_usd(value)


@pytest.mark.parametrize(
    "value,assumed_unit_seconds,expected",
    [
        (5, 60, 300),
        ("5m", 60, 300),
        ("300s", 60, 300),
        ("1h", 60, 3600),
        ("5", 60, 300),
    ],
)
def test_parse_duration_seconds(value, assumed_unit_seconds, expected):
    assert parse_duration_seconds(value, assumed_unit_seconds=assumed_unit_seconds) == expected


@pytest.mark.parametrize("value", ["forever", None, True])
def test_parse_duration_rejects_invalid(value):
    with pytest.raises(ValueError):
        parse_duration_seconds(value)
