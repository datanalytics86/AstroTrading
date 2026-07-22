"""Tests for regime classification (pure, no market I/O)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from astrotrading.quant.regime import classify_regime


def _series(values, start="2000-01-01", freq="7D"):
    idx = pd.date_range(start, periods=len(values), freq=freq)
    return pd.Series(values, index=idx)


def test_low_level_tends_favorable():
    # long history high, recent low
    hist = list(np.linspace(900, 1000, 200))
    recent = list(np.linspace(700, 680, 40))  # low & falling
    s = _series(hist + recent)
    reg = classify_regime(s, step_days=7)
    assert reg.label in ("Favorable", "Neutral")
    assert reg.percentile < 50
    assert reg.current_index == pytest.approx(680.0, abs=1.0)


def test_high_level_tends_unfavorable():
    hist = list(np.linspace(600, 700, 200))
    recent = list(np.linspace(950, 980, 40))  # high & rising
    s = _series(hist + recent)
    reg = classify_regime(s, step_days=7)
    assert reg.label in ("Desfavorable", "Neutral")
    assert reg.percentile > 50


def test_empty_raises():
    with pytest.raises(ValueError):
        classify_regime(pd.Series(dtype=float))


def test_justification_nonempty():
    s = _series(list(np.random.default_rng(0).normal(800, 50, 100)))
    reg = classify_regime(s)
    assert len(reg.justification) > 40
    assert reg.label in ("Favorable", "Neutral", "Desfavorable")
