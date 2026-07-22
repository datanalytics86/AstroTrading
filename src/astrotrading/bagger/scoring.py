"""
Pure scoring functions for the Bagger Scanner.

All pillar scores are in [0, 1]. Missing inputs return None so the engine
can re-normalize weights over available pillars (robust to incomplete yfinance data).

Literature mapping: see literature.py / SCORE_SOURCES.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .literature import PILLAR_META

# Public weight map (sum = 1.0)
PILLAR_WEIGHTS: dict[str, float] = {k: float(v["weight"]) for k, v in PILLAR_META.items()}

SCORE_SOURCES: dict[str, list[str]] = {k: list(v["sources"]) for k, v in PILLAR_META.items()}


def _clamp01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _safe_float(x: Any) -> float | None:
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def _piecewise_high_better(
    value: float | None,
    *,
    low: float,
    mid: float,
    high: float,
) -> float | None:
    """
    Map a metric to [0,1] where higher is better.
    ≤ low → 0; mid → 0.5; ≥ high → 1; linear between.
    """
    if value is None:
        return None
    if value <= low:
        return 0.0
    if value >= high:
        return 1.0
    if value <= mid:
        return 0.5 * (value - low) / (mid - low) if mid > low else 0.5
    return 0.5 + 0.5 * (value - mid) / (high - mid) if high > mid else 1.0


def _piecewise_low_better(
    value: float | None,
    *,
    best: float,
    mid: float,
    worst: float,
) -> float | None:
    """Lower is better (e.g. leverage, PEG). ≤ best → 1; ≥ worst → 0."""
    if value is None:
        return None
    if value <= best:
        return 1.0
    if value >= worst:
        return 0.0
    if value <= mid:
        return 1.0 - 0.5 * (value - best) / (mid - best) if mid > best else 0.5
    return 0.5 * (1.0 - (value - mid) / (worst - mid)) if worst > mid else 0.0


# ---------------------------------------------------------------------------
# Pillar scorers
# ---------------------------------------------------------------------------


def score_quality(
    *,
    roe: float | None = None,
    roic: float | None = None,
    profit_margin: float | None = None,
    debt_to_equity: float | None = None,
) -> tuple[float | None, list[str]]:
    """
    Capital efficiency / quality (Mayer, Fisher, Phelps).

    Prefers ROIC when available, else ROE. High margins; penalizes high leverage.
    """
    reasons: list[str] = []
    parts: list[tuple[float, float]] = []  # (weight, score)

    # Capital return: ROIC preferred (Mayer), ROE fallback
    cap = roic if roic is not None else roe
    cap_label = "ROIC" if roic is not None else "ROE"
    # yfinance ROE often as fraction (0.25) or percent (25) — normalize
    if cap is not None and abs(cap) > 1.5:
        cap = cap / 100.0
    s_cap = _piecewise_high_better(cap, low=0.05, mid=0.15, high=0.30)
    if s_cap is not None and cap is not None:
        parts.append((0.45, s_cap))
        reasons.append(f"{cap_label}={cap*100:.1f}% → quality {s_cap:.2f} (Mayer/Fisher).")

    # Margins
    pm = profit_margin
    if pm is not None and abs(pm) > 1.5:
        pm = pm / 100.0
    s_pm = _piecewise_high_better(pm, low=0.03, mid=0.12, high=0.25)
    if s_pm is not None and pm is not None:
        parts.append((0.30, s_pm))
        reasons.append(f"Profit margin={pm*100:.1f}% → {s_pm:.2f}.")

    # Leverage (debt/equity): lower better. yfinance often as percent (50 = 0.5)
    de = debt_to_equity
    if de is not None and de > 5:  # likely percent scale
        de = de / 100.0
    s_de = _piecewise_low_better(de, best=0.3, mid=1.0, worst=2.5)
    if s_de is not None and de is not None:
        parts.append((0.25, s_de))
        reasons.append(f"D/E={de:.2f} → leverage score {s_de:.2f} (lower better).")

    if not parts:
        return None, ["Quality: datos insuficientes (ROE/ROIC/márgenes/D-E)."]

    wsum = sum(w for w, _ in parts)
    score = sum(w * s for w, s in parts) / wsum
    return _clamp01(score), reasons


def score_growth(
    *,
    revenue_growth: float | None = None,
    earnings_growth: float | None = None,
    earnings_quarterly_growth: float | None = None,
) -> tuple[float | None, list[str]]:
    """
    Growth pillar (Mayer, O'Neil CAN SLIM A/C, Lynch).
    """
    reasons: list[str] = []
    parts: list[tuple[float, float]] = []

    def _norm_g(g: float | None) -> float | None:
        if g is None:
            return None
        # already fraction or percent
        return g / 100.0 if abs(g) > 1.5 else g

    rg = _norm_g(revenue_growth)
    eg = _norm_g(earnings_growth)
    qg = _norm_g(earnings_quarterly_growth)

    s_rg = _piecewise_high_better(rg, low=0.0, mid=0.12, high=0.30)
    if s_rg is not None and rg is not None:
        parts.append((0.35, s_rg))
        reasons.append(f"Revenue growth={rg*100:.1f}% → {s_rg:.2f} (Mayer/O'Neil).")

    s_eg = _piecewise_high_better(eg, low=0.0, mid=0.15, high=0.40)
    if s_eg is not None and eg is not None:
        parts.append((0.40, s_eg))
        reasons.append(f"Earnings growth={eg*100:.1f}% → {s_eg:.2f} (CAN SLIM A).")

    s_qg = _piecewise_high_better(qg, low=-0.05, mid=0.15, high=0.40)
    if s_qg is not None and qg is not None:
        parts.append((0.25, s_qg))
        reasons.append(f"Quarterly earnings growth={qg*100:.1f}% → {s_qg:.2f} (CAN SLIM C).")
        # Acceleration bonus note
        if eg is not None and qg > eg + 0.05:
            reasons.append("Aceleración de earnings (trimestral > anual) — O'Neil favorable.")

    if not parts:
        return None, ["Growth: sin datos de sales/EPS growth."]

    wsum = sum(w for w, _ in parts)
    score = sum(w * s for w, s in parts) / wsum
    # mild acceleration boost
    if eg is not None and qg is not None and qg > eg + 0.05:
        score = min(1.0, score + 0.05)
    return _clamp01(score), reasons


def score_momentum(
    *,
    rs_3m: float | None = None,
    rs_6m: float | None = None,
    rs_12m: float | None = None,
    pct_from_52w_high: float | None = None,
    above_50dma: bool | None = None,
    above_200dma: bool | None = None,
    sma50_above_sma200: bool | None = None,
) -> tuple[float | None, list[str]]:
    """
    Momentum / RS (O'Neil R, Minervini Trend Template).

    pct_from_52w_high: (price/high_52w - 1), e.g. -0.05 = 5% below high.
    """
    reasons: list[str] = []
    parts: list[tuple[float, float]] = []

    # Relative strength composite
    rs_vals = [v for v in (rs_3m, rs_6m, rs_12m) if v is not None]
    if rs_vals:
        # weight medium-term more (Minervini/O'Neil leadership)
        w3 = 0.25 if rs_3m is not None else 0.0
        w6 = 0.45 if rs_6m is not None else 0.0
        w12 = 0.30 if rs_12m is not None else 0.0
        wtot = w3 + w6 + w12
        rs_combo = (
            (w3 * (rs_3m or 0) + w6 * (rs_6m or 0) + w12 * (rs_12m or 0)) / wtot
        )
        # RS of +20% vs SPX → strong; -20% weak
        s_rs = _piecewise_high_better(rs_combo, low=-0.15, mid=0.05, high=0.25)
        if s_rs is not None:
            parts.append((0.45, s_rs))
            reasons.append(
                f"RS vs SPX (blend)={rs_combo*100:+.1f}% → {s_rs:.2f} (O'Neil R / Minervini)."
            )

    # Near 52-week high (Minervini: stocks near highs, not deep value basing only)
    if pct_from_52w_high is not None:
        # 0 = at high → 1; -0.30 → ~0
        s_hi = _piecewise_high_better(pct_from_52w_high, low=-0.35, mid=-0.10, high=-0.02)
        if s_hi is not None:
            parts.append((0.25, s_hi))
            reasons.append(
                f"Distancia a máximo 52s={pct_from_52w_high*100:+.1f}% → {s_hi:.2f} (Trend Template)."
            )

    # SMA structure
    trend_pts = 0.0
    trend_n = 0
    if above_50dma is True:
        trend_pts += 1.0
        trend_n += 1
        reasons.append("Precio > SMA50.")
    elif above_50dma is False:
        trend_n += 1
    if above_200dma is True:
        trend_pts += 1.0
        trend_n += 1
        reasons.append("Precio > SMA200.")
    elif above_200dma is False:
        trend_n += 1
    if sma50_above_sma200 is True:
        trend_pts += 1.0
        trend_n += 1
        reasons.append("SMA50 > SMA200 (stack alcista Minervini).")
    elif sma50_above_sma200 is False:
        trend_n += 1

    if trend_n > 0:
        s_tr = trend_pts / 3.0  # max 3 checks
        parts.append((0.30, s_tr))
        reasons.append(f"Estructura de tendencia {trend_pts:.0f}/3 → {s_tr:.2f}.")

    if not parts:
        return None, ["Momentum: sin precios suficientes."]

    wsum = sum(w for w, _ in parts)
    score = sum(w * s for w, s in parts) / wsum
    return _clamp01(score), reasons


def score_valuation(
    *,
    peg: float | None = None,
    trailing_pe: float | None = None,
    earnings_growth: float | None = None,
) -> tuple[float | None, list[str]]:
    """
    Valuation reasonableness (Lynch PEG, Mayer caution on extremes).
    """
    reasons: list[str] = []
    parts: list[tuple[float, float]] = []

    # PEG: Lynch sweet spot ~1; >2 expensive; <0 meaningless
    if peg is not None and peg > 0:
        s_peg = _piecewise_low_better(peg, best=0.8, mid=1.5, worst=3.0)
        if s_peg is not None:
            parts.append((0.60, s_peg))
            reasons.append(f"PEG={peg:.2f} → {s_peg:.2f} (Lynch GARP).")

    pe = trailing_pe
    if pe is not None and pe > 0:
        # bare PE without growth context is weak; still penalize extremes
        s_pe = _piecewise_low_better(pe, best=12.0, mid=28.0, worst=60.0)
        # If growth is exceptional, soften PE penalty (Mayer: growth can justify price)
        eg = earnings_growth
        if eg is not None:
            if abs(eg) > 1.5:
                eg = eg / 100.0
            if eg is not None and eg > 0.25 and s_pe is not None:
                s_pe = min(1.0, s_pe + 0.15)
                reasons.append("PE suavizado por growth >25% (Mayer).")
        if s_pe is not None:
            parts.append((0.40, s_pe))
            reasons.append(f"Trailing P/E={pe:.1f} → {s_pe:.2f}.")

    if not parts:
        return None, ["Valuation: sin PEG ni P/E útiles."]

    wsum = sum(w for w, _ in parts)
    score = sum(w * s for w, s in parts) / wsum
    return _clamp01(score), reasons


def score_bonus(
    *,
    insider_pct: float | None = None,
    buyback_yield: float | None = None,
    payout_ratio: float | None = None,
) -> tuple[float | None, list[str]]:
    """
    Qualitative bonus (Fisher/Mayer skin-in-game; buybacks).
    """
    reasons: list[str] = []
    parts: list[tuple[float, float]] = []

    ins = insider_pct
    if ins is not None:
        if ins > 1.5:  # percent
            ins = ins / 100.0
        s_ins = _piecewise_high_better(ins, low=0.01, mid=0.08, high=0.20)
        if s_ins is not None:
            parts.append((0.70, s_ins))
            reasons.append(f"Insider ownership={ins*100:.1f}% → {s_ins:.2f} (Fisher/Mayer).")

    if buyback_yield is not None and buyback_yield > 0:
        s_bb = _piecewise_high_better(buyback_yield, low=0.0, mid=0.02, high=0.05)
        if s_bb is not None:
            parts.append((0.30, s_bb))
            reasons.append(f"Buyback yield≈{buyback_yield*100:.1f}% → {s_bb:.2f}.")

    # mild positive if sustainable dividend (not a bagger requirement)
    if payout_ratio is not None and 0 < payout_ratio < 0.6:
        reasons.append(f"Payout ratio={payout_ratio:.0%} (dividendo sostenible, bonus menor).")
        if not parts:
            return 0.35, reasons
        # tiny lift handled by not zeroing

    if not parts:
        return None, ["Bonus: sin insider/buyback data."]

    wsum = sum(w for w, _ in parts)
    score = sum(w * s for w, s in parts) / wsum
    return _clamp01(score), reasons


@dataclass(slots=True)
class PillarScores:
    quality: float | None = None
    growth: float | None = None
    momentum: float | None = None
    valuation: float | None = None
    bonus: float | None = None
    reasons: dict[str, list[str]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, float | None]:
        return {
            "quality": self.quality,
            "growth": self.growth,
            "momentum": self.momentum,
            "valuation": self.valuation,
            "bonus": self.bonus,
        }


def composite_score(
    pillars: PillarScores,
    weights: dict[str, float] | None = None,
) -> tuple[float, dict[str, float], list[str]]:
    """
    Weighted composite with re-normalization over available pillars.

    Returns (score_0_100, used_weights, summary_reasons).
    """
    w = dict(weights or PILLAR_WEIGHTS)
    values = pillars.as_dict()
    available = {k: v for k, v in values.items() if v is not None}
    if not available:
        return 0.0, {}, ["Sin pilares puntuables."]

    w_avail = {k: w.get(k, 0.0) for k in available}
    wsum = sum(w_avail.values())
    if wsum <= 0:
        # equal weight fallback
        w_avail = {k: 1.0 / len(available) for k in available}
        wsum = 1.0
    else:
        w_avail = {k: v / wsum for k, v in w_avail.items()}

    score01 = sum(w_avail[k] * float(available[k]) for k in available)
    score100 = round(100.0 * _clamp01(score01), 2)

    summary: list[str] = []
    for k in ("quality", "growth", "momentum", "valuation", "bonus"):
        if k in available:
            summary.append(
                f"{PILLAR_META[k]['label']}: {available[k]:.2f} "
                f"(peso efectivo {w_avail[k]*100:.0f}%)"
            )
            for r in (pillars.reasons.get(k) or [])[:3]:
                summary.append(f"  · {r}")

    return score100, w_avail, summary


def score_from_metrics(metrics: dict[str, Any]) -> tuple[float, PillarScores, dict[str, float], list[str]]:
    """
    End-to-end pure scoring from a flat metrics dict.

    Expected keys (all optional):
      roe, roic, profit_margin, debt_to_equity,
      revenue_growth, earnings_growth, earnings_quarterly_growth,
      rs_3m, rs_6m, rs_12m, pct_from_52w_high,
      above_50dma, above_200dma, sma50_above_sma200,
      peg, trailing_pe, insider_pct, buyback_yield, payout_ratio
    """
    q, rq = score_quality(
        roe=_safe_float(metrics.get("roe")),
        roic=_safe_float(metrics.get("roic")),
        profit_margin=_safe_float(metrics.get("profit_margin")),
        debt_to_equity=_safe_float(metrics.get("debt_to_equity")),
    )
    g, rg = score_growth(
        revenue_growth=_safe_float(metrics.get("revenue_growth")),
        earnings_growth=_safe_float(metrics.get("earnings_growth")),
        earnings_quarterly_growth=_safe_float(metrics.get("earnings_quarterly_growth")),
    )
    m, rm = score_momentum(
        rs_3m=_safe_float(metrics.get("rs_3m")),
        rs_6m=_safe_float(metrics.get("rs_6m")),
        rs_12m=_safe_float(metrics.get("rs_12m")),
        pct_from_52w_high=_safe_float(metrics.get("pct_from_52w_high")),
        above_50dma=metrics.get("above_50dma"),
        above_200dma=metrics.get("above_200dma"),
        sma50_above_sma200=metrics.get("sma50_above_sma200"),
    )
    v, rv = score_valuation(
        peg=_safe_float(metrics.get("peg")),
        trailing_pe=_safe_float(metrics.get("trailing_pe")),
        earnings_growth=_safe_float(metrics.get("earnings_growth")),
    )
    b, rb = score_bonus(
        insider_pct=_safe_float(metrics.get("insider_pct")),
        buyback_yield=_safe_float(metrics.get("buyback_yield")),
        payout_ratio=_safe_float(metrics.get("payout_ratio")),
    )

    pillars = PillarScores(
        quality=q,
        growth=g,
        momentum=m,
        valuation=v,
        bonus=b,
        reasons={
            "quality": rq,
            "growth": rg,
            "momentum": rm,
            "valuation": rv,
            "bonus": rb,
        },
    )
    total, used_w, summary = composite_score(pillars)
    return total, pillars, used_w, summary
