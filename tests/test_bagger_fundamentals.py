"""Tests for fundamental extraction correctness (no network)."""

from __future__ import annotations

from astrotrading.bagger.engine import _extract_fundamentals


def test_does_not_double_count_quarterly_as_annual():
    info = {
        "shortName": "Test Co",
        "earningsQuarterlyGrowth": 0.40,
        # annual missing on purpose
    }
    m = _extract_fundamentals(info)
    assert m["earnings_growth"] is None
    assert m["earnings_quarterly_growth"] == 0.40


def test_annual_and_quarterly_independent():
    info = {
        "earningsGrowth": 0.20,
        "earningsQuarterlyGrowth": 0.35,
    }
    m = _extract_fundamentals(info)
    assert m["earnings_growth"] == 0.20
    assert m["earnings_quarterly_growth"] == 0.35


def test_never_labels_roa_as_roic():
    info = {
        "returnOnAssets": 0.12,
        "returnOnEquity": 0.25,
    }
    m = _extract_fundamentals(info)
    assert m["roic"] is None
    assert m["roe"] == 0.25


def test_trailing_pe_not_forward():
    info = {"forwardPE": 18.0}
    m = _extract_fundamentals(info)
    assert m["trailing_pe"] is None


def test_true_roic_used():
    info = {"returnOnCapital": 0.22, "returnOnEquity": 0.30}
    m = _extract_fundamentals(info)
    assert m["roic"] == 0.22
