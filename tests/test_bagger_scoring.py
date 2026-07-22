"""Unit tests for Bagger Scanner pure scoring (no network)."""

from __future__ import annotations

import pytest

from astrotrading.bagger.scoring import (
    PILLAR_WEIGHTS,
    composite_score,
    score_from_metrics,
    score_growth,
    score_momentum,
    score_quality,
    score_valuation,
    PillarScores,
)


def test_pillar_weights_sum_to_one():
    assert sum(PILLAR_WEIGHTS.values()) == pytest.approx(1.0, abs=1e-9)


def test_quality_high_roe_high_margin():
    s, reasons = score_quality(roe=0.28, profit_margin=0.22, debt_to_equity=0.4)
    assert s is not None and s > 0.7
    assert any("ROE" in r or "ROIC" in r for r in reasons)


def test_quality_missing_returns_none():
    s, reasons = score_quality()
    assert s is None
    assert reasons


def test_growth_strong():
    s, _ = score_growth(revenue_growth=0.25, earnings_growth=0.35, earnings_quarterly_growth=0.40)
    assert s is not None and s > 0.7


def test_momentum_minervini_like():
    s, reasons = score_momentum(
        rs_3m=0.10,
        rs_6m=0.18,
        rs_12m=0.22,
        pct_from_52w_high=-0.03,
        above_50dma=True,
        above_200dma=True,
        sma50_above_sma200=True,
    )
    assert s is not None and s > 0.7
    assert any("SMA" in r or "Trend" in r or "RS" in r for r in reasons)


def test_valuation_peg_lynch():
    s_good, _ = score_valuation(peg=0.9, trailing_pe=18)
    s_bad, _ = score_valuation(peg=3.5, trailing_pe=80)
    assert s_good is not None and s_bad is not None
    assert s_good > s_bad


def test_composite_renormalizes_missing():
    pillars = PillarScores(quality=0.8, growth=0.7, momentum=None, valuation=0.6, bonus=None)
    total, used, summary = composite_score(pillars)
    assert 0 < total <= 100
    assert "momentum" not in used
    assert abs(sum(used.values()) - 1.0) < 1e-9
    assert summary


def test_score_from_metrics_end_to_end():
    metrics = {
        "roe": 0.25,
        "profit_margin": 0.18,
        "debt_to_equity": 0.5,
        "revenue_growth": 0.20,
        "earnings_growth": 0.25,
        "earnings_quarterly_growth": 0.30,
        "rs_6m": 0.12,
        "rs_12m": 0.15,
        "pct_from_52w_high": -0.05,
        "above_50dma": True,
        "above_200dma": True,
        "sma50_above_sma200": True,
        "peg": 1.1,
        "trailing_pe": 22,
        "insider_pct": 0.12,
    }
    total, pillars, used_w, summary = score_from_metrics(metrics)
    assert total >= 50
    assert pillars.quality is not None
    assert pillars.growth is not None
    assert pillars.momentum is not None
    assert len(summary) >= 3


def test_percent_scale_roe_normalized():
    # yfinance sometimes returns 25 for 25%
    s1, _ = score_quality(roe=0.25)
    s2, _ = score_quality(roe=25.0)
    assert s1 is not None and s2 is not None
    assert s1 == pytest.approx(s2, abs=0.05)
