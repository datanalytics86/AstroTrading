"""Tests for Cyclic Index 50y forecast (math + summary; ephemeris optional)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from astrotrading.astrology.forecast import (
    DE421_END,
    FORECAST_KERNEL,
    find_local_extrema,
    forecast_end_date,
    kernel_coverage_note,
    summarize_forecast,
)


def test_forecast_end_date_50y():
    end = forecast_end_date(date(2026, 7, 22), years=50)
    assert end == date(2076, 7, 22)


def test_de421_insufficient_for_50y_from_2026():
    start = date(2026, 7, 22)
    end = forecast_end_date(start, years=50)
    assert end > DE421_END
    assert "DE440" in FORECAST_KERNEL.upper() or "440" in FORECAST_KERNEL


def test_kernel_coverage_note():
    note = kernel_coverage_note()
    assert "DE421" in note
    assert "DE440" in note or "de440" in note


def test_find_local_extrema():
    # synthetic sine-like series
    idx = pd.date_range("2030-01-01", periods=200, freq="14D")
    import numpy as np

    y = 800 + 100 * np.sin(np.linspace(0, 6 * np.pi, len(idx)))
    s = pd.Series(y, index=idx)
    ext = find_local_extrema(s, order=5, max_count=6)
    assert len(ext) >= 2
    kinds = {e.kind for e in ext}
    assert "min" in kinds or "max" in kinds


def test_summarize_forecast():
    idx = pd.date_range("2026-01-01", periods=100, freq="14D")
    import numpy as np

    y = 850 - np.linspace(0, 80, len(idx))  # declining → compression
    df = pd.DataFrame({"date": idx, "cyclic_index": y})
    summary = summarize_forecast(df, step_days=14)
    assert summary.trend_label == "compresión"
    assert summary.forecast_min <= summary.forecast_max
    assert summary.current_index == pytest.approx(y[0], abs=0.1)
    assert "orbital" in summary.disclaimer.lower() or "mercados" in summary.disclaimer.lower()


@pytest.mark.slow
def test_live_forecast_short_horizon():
    """Optional integration: 2y forecast with DE440s (network/kernel)."""
    from astrotrading.astrology.forecast import compute_cyclic_index_forecast

    df = compute_cyclic_index_forecast(years=2, step_days=30, frame="heliocentric")
    assert len(df) >= 20
    assert df["cyclic_index"].between(0, 1800).all()
