"""
Bagger Scanner engine — multi-bagger candidate ranking.

Pipeline:
  1. Optional market-regime gate (Alfayate macro + optional Cyclic Index label).
  2. Pull price history (batch) + fundamentals (per ticker, best-effort).
  3. Score each name on literature-aligned pillars.
  4. Return ranked candidates with transparent reasons.

Not investment advice. Research tool for a private dashboard.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

import numpy as np
import pandas as pd

from .scoring import PillarScores, score_from_metrics
from .universe import DEFAULT_BAGGER_UNIVERSE, resolve_universe

logger = logging.getLogger(__name__)

RegimeContext = Literal["Favorable", "Neutral", "Desfavorable", "Risk-On", "Risk-Off", "Unknown"]


@dataclass(frozen=True, slots=True)
class BaggerCandidate:
    symbol: str
    rank: int
    score: float
    name: str | None
    sector: str | None
    industry: str | None
    pillars: dict[str, float | None]
    used_weights: dict[str, float]
    metrics: dict[str, Any]
    reasons: list[str]
    literature_tags: list[str]

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "rank": self.rank,
            "score": self.score,
            "name": self.name,
            "sector": self.sector,
            "industry": self.industry,
            "pillars": self.pillars,
            "used_weights": self.used_weights,
            "metrics": self.metrics,
            "reasons": self.reasons,
            "literature_tags": self.literature_tags,
        }


@dataclass(frozen=True, slots=True)
class BaggerResult:
    as_of: str
    universe_size: int
    scanned: int
    candidates: list[BaggerCandidate]
    regime_label: str
    regime_warning: str | None
    regime_reasons: list[str]
    notes: str
    pillar_weights: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "as_of": self.as_of,
            "universe_size": self.universe_size,
            "scanned": self.scanned,
            "regime_label": self.regime_label,
            "regime_warning": self.regime_warning,
            "regime_reasons": self.regime_reasons,
            "notes": self.notes,
            "pillar_weights": self.pillar_weights,
            "candidates": [c.to_dict() for c in self.candidates],
        }


# ---------------------------------------------------------------------------
# Price helpers (shared patterns with alfayate)
# ---------------------------------------------------------------------------


def _last_return(close: pd.Series, days: int) -> float:
    s = close.dropna()
    if len(s) < days + 1:
        return float("nan")
    return float(s.iloc[-1] / s.iloc[-(days + 1)] - 1.0)


def _sma(close: pd.Series, window: int) -> float:
    s = close.dropna()
    if len(s) < window:
        return float("nan")
    return float(s.iloc[-window:].mean())


def _download_closes(tickers: list[str], start: str) -> pd.DataFrame:
    import yfinance as yf

    if not tickers:
        return pd.DataFrame()
    data = yf.download(
        tickers,
        start=start,
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="column",
    )
    if data is None or data.empty:
        return pd.DataFrame()

    if len(tickers) == 1:
        if "Close" in data.columns:
            out = data[["Close"]].copy()
            out.columns = tickers
            return out
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):
        lvl0 = data.columns.get_level_values(0)
        if "Close" in lvl0:
            return data["Close"].copy()
        if "Adj Close" in lvl0:
            return data["Adj Close"].copy()
        try:
            return data.xs("Close", axis=1, level=1)
        except Exception:
            return pd.DataFrame()
    return data


def _price_features(px: pd.Series, spx: pd.Series) -> dict[str, Any]:
    px = px.dropna()
    spx = spx.dropna()
    out: dict[str, Any] = {}
    if len(px) < 60:
        return out

    last = float(px.iloc[-1])
    sma50 = _sma(px, 50)
    sma200 = _sma(px, 200)
    out["price"] = last
    out["above_50dma"] = bool(np.isfinite(sma50) and last > sma50) if np.isfinite(sma50) else None
    out["above_200dma"] = bool(np.isfinite(sma200) and last > sma200) if np.isfinite(sma200) else None
    if np.isfinite(sma50) and np.isfinite(sma200):
        out["sma50_above_sma200"] = bool(sma50 > sma200)

    # 52-week high (approx 252 sessions)
    window = min(252, len(px))
    high_52 = float(px.iloc[-window:].max())
    if high_52 > 0:
        out["pct_from_52w_high"] = last / high_52 - 1.0
        out["high_52w"] = high_52

    m3, m6, m12 = _last_return(px, 63), _last_return(px, 126), _last_return(px, 252)
    s3, s6, s12 = _last_return(spx, 63), _last_return(spx, 126), _last_return(spx, 252)
    if np.isfinite(m3) and np.isfinite(s3):
        out["rs_3m"] = m3 - s3
        out["mom_3m"] = m3
    if np.isfinite(m6) and np.isfinite(s6):
        out["rs_6m"] = m6 - s6
        out["mom_6m"] = m6
    if np.isfinite(m12) and np.isfinite(s12):
        out["rs_12m"] = m12 - s12
        out["mom_12m"] = m12
    return out


def _extract_fundamentals(info: dict) -> dict[str, Any]:
    """Map yfinance .info fields → scoring metrics (best-effort)."""
    if not info:
        return {}

    def g(*keys: str) -> Any:
        for k in keys:
            v = info.get(k)
            if v is not None:
                return v
        return None

    # Only true ROIC when present — never mislabel ROA as ROIC (Mayer cares about ROIC)
    roe = g("returnOnEquity")
    roic = g("returnOnCapital")
    # Prefer net margin; fall back to operating margin under same key (documented in reasons via scoring)
    margin = g("profitMargins")
    if margin is None:
        margin = g("operatingMargins")

    # CRITICAL: do not fall back annual earningsGrowth → quarterly (would double-count
    # the same quarterly figure in both growth sub-scores).
    earnings_growth = g("earningsGrowth")
    earnings_q = g("earningsQuarterlyGrowth")

    metrics = {
        "name": g("shortName", "longName"),
        "sector": g("sector"),
        "industry": g("industry"),
        "roe": roe,
        "roic": roic,
        "profit_margin": margin,
        "debt_to_equity": g("debtToEquity"),
        "revenue_growth": g("revenueGrowth"),
        "earnings_growth": earnings_growth,
        "earnings_quarterly_growth": earnings_q,
        "peg": g("pegRatio"),
        # trailing only — never substitute forwardPE (would mis-score valuation)
        "trailing_pe": g("trailingPE"),
        "insider_pct": g("heldPercentInsiders"),
        "payout_ratio": g("payoutRatio"),
        "market_cap": g("marketCap"),
        "beta": g("beta"),
        "buyback_yield": g("buybackYield"),
    }
    return metrics


def _fetch_ticker_info(symbol: str) -> dict[str, Any]:
    import yfinance as yf

    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        if not info or len(info) < 5:
            # fast_info fallback is limited
            try:
                fi = t.fast_info
                info = {
                    "shortName": symbol,
                    "lastPrice": getattr(fi, "last_price", None),
                    "marketCap": getattr(fi, "market_cap", None),
                }
            except Exception:
                info = {"shortName": symbol}
        return _extract_fundamentals(info)
    except Exception as exc:
        logger.debug("Fundamentals failed for %s: %s", symbol, exc)
        return {"name": symbol}


def _literature_tags(pillars: PillarScores) -> list[str]:
    tags: list[str] = []
    if pillars.quality is not None and pillars.quality >= 0.65:
        tags.append("Mayer/Fisher quality")
    if pillars.growth is not None and pillars.growth >= 0.65:
        tags.append("O'Neil/Lynch growth")
    if pillars.momentum is not None and pillars.momentum >= 0.65:
        tags.append("Minervini/O'Neil RS")
    if pillars.valuation is not None and pillars.valuation >= 0.65:
        tags.append("Lynch PEG OK")
    if pillars.bonus is not None and pillars.bonus >= 0.5:
        tags.append("Insider/owner bonus")
    return tags


def _assess_regime() -> tuple[str, list[str], str | None]:
    """Reuse Alfayate macro regime; soft warning if Risk-Off."""
    try:
        from astrotrading.alfayate.engine import assess_macro_regime

        label, score, reasons, _spx = assess_macro_regime()
        warning = None
        if label == "Risk-Off":
            warning = (
                "Régimen macro Risk-Off (Alfayate): O'Neil enfatiza no pelear el mercado. "
                "El ranking se muestra, pero la probabilidad de multi-baggers nuevos cae "
                "en mercados bajistas."
            )
        elif label == "Neutral":
            warning = (
                "Régimen Neutral: se permiten baggers, con más selectividad en momentum."
            )
        return label, reasons, warning
    except Exception as exc:
        logger.warning("Regime assessment failed: %s", exc)
        return "Unknown", [f"No se pudo evaluar régimen: {exc}"], None


def run_bagger_scanner(
    universe: list[str] | None = None,
    *,
    top_n: int = 25,
    min_score: float = 0.0,
    max_workers: int = 8,
    include_regime: bool = True,
) -> BaggerResult:
    """
    Run the full Bagger Scanner.

    Parameters
    ----------
    universe : optional ticker list (default ~200 liquid US names)
    top_n : max candidates returned
    min_score : filter threshold on 0–100 composite
    max_workers : thread pool for fundamentals
    include_regime : attach Alfayate macro gate/warning
    """
    from .scoring import PILLAR_WEIGHTS

    uni = resolve_universe(universe) if universe is None else list(dict.fromkeys(universe))
    as_of = date.today().isoformat()

    if include_regime:
        regime_label, regime_reasons, regime_warning = _assess_regime()
    else:
        regime_label, regime_reasons, regime_warning = "Unknown", [], None

    start = (date.today() - timedelta(days=420)).isoformat()
    tickers = list(uni)
    # batch prices including SPX
    closes = _download_closes(tickers + ["^GSPC"], start)
    if closes.empty or "^GSPC" not in closes.columns:
        return BaggerResult(
            as_of=as_of,
            universe_size=len(uni),
            scanned=0,
            candidates=[],
            regime_label=regime_label,
            regime_warning=regime_warning,
            regime_reasons=regime_reasons,
            notes="No se pudieron descargar precios (yfinance).",
            pillar_weights=dict(PILLAR_WEIGHTS),
        )

    spx = closes["^GSPC"].dropna()
    symbols = [c for c in closes.columns if c != "^GSPC"]

    # Fundamentals in parallel (I/O bound)
    fund_map: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {pool.submit(_fetch_ticker_info, sym): sym for sym in symbols}
        for fut in as_completed(futs):
            sym = futs[fut]
            try:
                fund_map[sym] = fut.result()
            except Exception:
                fund_map[sym] = {"name": sym}

    scored: list[tuple[float, BaggerCandidate]] = []
    scanned = 0

    for sym in symbols:
        px = closes[sym]
        if px.dropna().shape[0] < 100:
            continue
        scanned += 1
        price_m = _price_features(px, spx)
        fund = fund_map.get(sym) or {}
        metrics = {**fund, **price_m}

        total, pillars, used_w, summary = score_from_metrics(metrics)
        if total < min_score:
            continue

        # Compact metrics for UI
        slim_metrics = {
            k: metrics.get(k)
            for k in (
                "price",
                "roe",
                "roic",
                "profit_margin",
                "debt_to_equity",
                "revenue_growth",
                "earnings_growth",
                "earnings_quarterly_growth",
                "peg",
                "trailing_pe",
                "rs_3m",
                "rs_6m",
                "rs_12m",
                "pct_from_52w_high",
                "above_50dma",
                "above_200dma",
                "sma50_above_sma200",
                "insider_pct",
                "market_cap",
                "sector",
                "industry",
            )
            if metrics.get(k) is not None
        }

        cand = BaggerCandidate(
            symbol=sym,
            rank=0,
            score=total,
            name=fund.get("name"),
            sector=fund.get("sector"),
            industry=fund.get("industry"),
            pillars=pillars.as_dict(),
            used_weights=used_w,
            metrics=slim_metrics,
            reasons=summary,
            literature_tags=_literature_tags(pillars),
        )
        scored.append((total, cand))

    scored.sort(key=lambda x: x[0], reverse=True)
    ranked: list[BaggerCandidate] = []
    for i, (sc, c) in enumerate(scored[:top_n], start=1):
        ranked.append(
            BaggerCandidate(
                symbol=c.symbol,
                rank=i,
                score=c.score,
                name=c.name,
                sector=c.sector,
                industry=c.industry,
                pillars=c.pillars,
                used_weights=c.used_weights,
                metrics=c.metrics,
                reasons=c.reasons,
                literature_tags=c.literature_tags,
            )
        )

    notes = (
        "Score 0–100 = suma ponderada de pilares literarios "
        "(Quality 30%, Growth 25%, Momentum 25%, Valuation 15%, Bonus 5%), "
        "renormalizado si faltan datos. "
        "No predice 100-baggers; filtra nombres con perfil compatible con la bibliografía."
    )
    if regime_warning:
        notes = regime_warning + " " + notes

    return BaggerResult(
        as_of=as_of,
        universe_size=len(uni),
        scanned=scanned,
        candidates=ranked,
        regime_label=regime_label,
        regime_warning=regime_warning,
        regime_reasons=regime_reasons,
        notes=notes,
        pillar_weights=dict(PILLAR_WEIGHTS),
    )
