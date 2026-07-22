"""
Regime classification for the Barbault Cyclic Index.

MVP heuristic (transparent, not a black box):
  - Level: percentile of current index vs full history (low = concentration).
  - Momentum: slope of index over ~1y and ~2y windows.
  - Composite score → Favorable / Neutral / Desfavorable.

Heuristic reading used in this dashboard (transparent, not Barbault orthodoxy):
  Lower cyclic index → outer planets more clustered (smaller mutual arcs).
  Higher index → greater angular dispersion among the five slow planets.

  The Favorable/Neutral/Desfavorable labels are **research heuristics** for the
  private dashboard (low level + non-rising slope → "Favorable" in this app).
  They are NOT a market forecast and NOT a claim of historical inevitability.

This is a research dashboard signal, not investment advice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

RegimeLabel = Literal["Favorable", "Neutral", "Desfavorable"]


@dataclass(frozen=True, slots=True)
class RegimeSignal:
    label: RegimeLabel
    score: float  # -1 (very unfavorable) … +1 (very favorable)
    percentile: float  # 0–100 of current level in history (low level = low pct)
    zscore: float
    slope_1y: float  # index points per year
    slope_2y: float
    current_index: float
    as_of: str
    justification: str
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "score": self.score,
            "percentile": self.percentile,
            "zscore": self.zscore,
            "slope_1y": self.slope_1y,
            "slope_2y": self.slope_2y,
            "current_index": self.current_index,
            "as_of": self.as_of,
            "justification": self.justification,
            "context": self.context,
        }


def _ols_slope(y: np.ndarray, days_per_step: float = 7.0) -> float:
    """Slope in index-points per year given evenly-ish sampled series."""
    n = len(y)
    if n < 3:
        return 0.0
    x = np.arange(n, dtype=float)
    # deg=1 polyfit
    coef = np.polyfit(x, y, 1)
    slope_per_step = float(coef[0])
    steps_per_year = 365.25 / days_per_step
    return slope_per_step * steps_per_year


def classify_regime(
    series: pd.Series,
    *,
    step_days: int = 7,
    low_pct_threshold: float = 35.0,
    high_pct_threshold: float = 65.0,
) -> RegimeSignal:
    """
    Classify current regime from a Cyclic Index time series.

    Parameters
    ----------
    series : pd.Series
        Index = dates, values = cyclic index levels. Must be sorted ascending.
    """
    s = series.dropna().sort_index()
    if s.empty:
        raise ValueError("Empty cyclic index series")

    current = float(s.iloc[-1])
    as_of = pd.Timestamp(s.index[-1]).date().isoformat()

    # Level stats
    percentile = float((s <= current).mean() * 100.0)
    mu = float(s.mean())
    sigma = float(s.std(ddof=1)) or 1.0
    zscore = (current - mu) / sigma

    # Windows (~1y and ~2y in steps)
    steps_1y = max(3, int(round(365 / step_days)))
    steps_2y = max(5, int(round(730 / step_days)))
    window_1y = s.iloc[-steps_1y:] if len(s) >= steps_1y else s
    window_2y = s.iloc[-steps_2y:] if len(s) >= steps_2y else s
    slope_1y = _ols_slope(window_1y.to_numpy(dtype=float), days_per_step=step_days)
    slope_2y = _ols_slope(window_2y.to_numpy(dtype=float), days_per_step=step_days)

    # Score components in [-1, 1]
    # Low percentile (clustered planets) → positive
    level_score = float(np.clip((50.0 - percentile) / 50.0, -1.0, 1.0))
    # Rising index → negative (dispersion increasing)
    slope_norm = float(np.clip(-(slope_1y) / 80.0, -1.0, 1.0))  # ~80 pts/year scale
    score = 0.65 * level_score + 0.35 * slope_norm

    if score >= 0.25 and percentile <= low_pct_threshold:
        label: RegimeLabel = "Favorable"
    elif score <= -0.25 and percentile >= high_pct_threshold:
        label = "Desfavorable"
    elif score >= 0.35:
        label = "Favorable"
    elif score <= -0.35:
        label = "Desfavorable"
    else:
        label = "Neutral"

    # Historical context: min/max and recent extremes
    hist_min = float(s.min())
    hist_max = float(s.max())
    hist_min_date = pd.Timestamp(s.idxmin()).date().isoformat()
    hist_max_date = pd.Timestamp(s.idxmax()).date().isoformat()

    direction = "ascendente" if slope_1y > 5 else ("descendente" if slope_1y < -5 else "lateral")
    justification = (
        f"Índice actual = {current:.1f}° (percentil {percentile:.0f}% del histórico, "
        f"z-score {zscore:+.2f}). Media histórica {mu:.1f}° ± {sigma:.1f}°. "
        f"Pendiente ~1 año: {slope_1y:+.1f}°/año ({direction}); "
        f"~2 años: {slope_2y:+.1f}°/año. "
    )
    if label == "Favorable":
        justification += (
            "Régimen Favorable: el índice se sitúa en zona baja/media-baja "
            "(menor dispersión angular de planetas lentos) y/o con pendiente no alcista."
        )
    elif label == "Desfavorable":
        justification += (
            "Régimen Desfavorable: el índice está en zona alta "
            "(mayor dispersión de los planetas exteriores) y/o con pendiente alcista marcada."
        )
    else:
        justification += (
            "Régimen Neutral: nivel y momentum del índice no muestran un sesgo claro "
            "respecto al histórico de referencia."
        )

    return RegimeSignal(
        label=label,
        score=round(score, 4),
        percentile=round(percentile, 2),
        zscore=round(zscore, 3),
        slope_1y=round(slope_1y, 2),
        slope_2y=round(slope_2y, 2),
        current_index=round(current, 4),
        as_of=as_of,
        justification=justification,
        context={
            "hist_mean": round(mu, 2),
            "hist_std": round(sigma, 2),
            "hist_min": round(hist_min, 2),
            "hist_min_date": hist_min_date,
            "hist_max": round(hist_max, 2),
            "hist_max_date": hist_max_date,
            "n_obs": int(len(s)),
        },
    )
