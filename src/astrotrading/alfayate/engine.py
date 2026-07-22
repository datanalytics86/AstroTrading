"""
Alfayate Engine (MVP) — top-down relative strength / momentum ranking.

Style inspired by Javier Alfayate's intermarket + breadth + trend framework:

  1. Macro / cycle regime first (intermarket ratios + index trend + breadth proxy).
  2. Only then rank "winning stocks" by relative strength / momentum within a universe.

MVP scope (honest about limits):
  - Intermarket: SPX vs Gold, SPX vs TLT (bonds), risk-on proxy via BTC optional.
  - Trend: SPX above/below 50d & 200d SMA, slope of 200d.
  - Breadth proxy: % of universe stocks above 50d and 200d SMA (when universe available).
  - Stock ranking: 3m / 6m / 12m RS vs SPX + absolute momentum, trend filter.

This is a research tool for a private dashboard — not a trade recommendation system.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MacroLabel = Literal["Risk-On", "Neutral", "Risk-Off"]


# Liquid large-cap / sector-representative universe (MVP subset; easy to expand).
DEFAULT_UNIVERSE: tuple[str, ...] = (
    # Megacaps / leaders
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "BRK-B", "JPM",
    "V", "UNH", "XOM", "LLY", "MA", "COST", "HD", "PG", "JNJ", "ABBV",
    "CRM", "ORCL", "BAC", "WMT", "CVX", "MRK", "KO", "PEP", "AMD", "NFLX",
    "ADBE", "CSCO", "ACN", "TMO", "MCD", "INTC", "IBM", "CAT", "GE", "GS",
    "AXP", "MS", "BA", "DIS", "PFE", "PM", "NEE", "TXN", "QCOM", "INTU",
    "AMAT", "ISRG", "BKNG", "NOW", "UBER", "SPGI", "BLK", "SYK", "DE", "LOW",
    "LRCX", "TJX", "GILD", "MDT", "ADI", "VRTX", "PANW", "SBUX", "PLD", "CB",
    "MMC", "SO", "CI", "BMY", "MO", "DUK", "EQIX", "SHW", "ZTS", "CME",
    "PH", "BSX", "KLAC", "SNPS", "CDNS", "ANET", "APH", "TDG", "TT", "CMG",
)


@dataclass(frozen=True, slots=True)
class StockCandidate:
    symbol: str
    rank: int
    score: float
    rs_3m: float
    rs_6m: float
    rs_12m: float
    mom_6m: float
    above_50dma: bool
    above_200dma: bool
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AlfayateResult:
    as_of: str
    macro_label: MacroLabel
    macro_score: float
    macro_reasons: list[str]
    breadth_above_50: float | None
    breadth_above_200: float | None
    candidates: list[StockCandidate]
    universe_size: int
    notes: str

    def to_dict(self) -> dict:
        return {
            "as_of": self.as_of,
            "macro_label": self.macro_label,
            "macro_score": self.macro_score,
            "macro_reasons": self.macro_reasons,
            "breadth_above_50": self.breadth_above_50,
            "breadth_above_200": self.breadth_above_200,
            "universe_size": self.universe_size,
            "notes": self.notes,
            "candidates": [
                {
                    "symbol": c.symbol,
                    "rank": c.rank,
                    "score": c.score,
                    "rs_3m": c.rs_3m,
                    "rs_6m": c.rs_6m,
                    "rs_12m": c.rs_12m,
                    "mom_6m": c.mom_6m,
                    "above_50dma": c.above_50dma,
                    "above_200dma": c.above_200dma,
                    "reasons": c.reasons,
                }
                for c in self.candidates
            ],
        }


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
        # single ticker → flat columns
        if "Close" in data.columns:
            out = data[["Close"]].copy()
            out.columns = tickers
            return out
        return pd.DataFrame()

    # Multi-ticker: columns often MultiIndex (Price, Ticker)
    if isinstance(data.columns, pd.MultiIndex):
        # Prefer Close level
        if "Close" in data.columns.get_level_values(0):
            closes = data["Close"].copy()
        elif "Adj Close" in data.columns.get_level_values(0):
            closes = data["Adj Close"].copy()
        else:
            # try second level layout (Ticker, Price)
            try:
                closes = data.xs("Close", axis=1, level=1)
            except Exception:
                closes = data.iloc[:, data.columns.get_level_values(-1) == "Close"]
                if isinstance(closes.columns, pd.MultiIndex):
                    closes.columns = closes.columns.get_level_values(0)
        return closes
    return data


def assess_macro_regime(start: str | None = None) -> tuple[MacroLabel, float, list[str], pd.Series | None]:
    """
    Top-down macro regime from intermarket + trend.
    Returns (label, score in [-1,1], reasons, spx_close_series).
    """
    start = start or (date.today() - timedelta(days=400)).isoformat()
    tickers = ["^GSPC", "GC=F", "TLT", "HYG", "BTC-USD"]
    closes = _download_closes(tickers, start)
    reasons: list[str] = []
    score = 0.0
    weights_hit = 0.0

    if closes.empty or "^GSPC" not in closes.columns:
        return "Neutral", 0.0, ["Sin datos de SPX — régimen indeterminado."], None

    spx = closes["^GSPC"].dropna()
    last = float(spx.iloc[-1])
    sma50 = _sma(spx, 50)
    sma200 = _sma(spx, 200)
    ret_3m = _last_return(spx, 63)
    ret_6m = _last_return(spx, 126)

    # Trend
    if np.isfinite(sma50) and np.isfinite(sma200):
        if last > sma50 > sma200:
            score += 0.35
            reasons.append(f"SPX en tendencia alcista (precio > SMA50 > SMA200; last={last:.0f}).")
        elif last < sma50 < sma200:
            score -= 0.35
            reasons.append("SPX en tendencia bajista (precio < SMA50 < SMA200).")
        elif last > sma200:
            score += 0.1
            reasons.append("SPX por encima de SMA200 (sesgo alcista de fondo, sin alineación perfecta).")
        else:
            score -= 0.1
            reasons.append("SPX por debajo de SMA200 (sesgo bajista de fondo).")
        weights_hit += 0.35

    if np.isfinite(ret_3m):
        if ret_3m > 0.05:
            score += 0.15
            reasons.append(f"Momentum SPX 3m = {ret_3m*100:+.1f}%.")
        elif ret_3m < -0.05:
            score -= 0.15
            reasons.append(f"Momentum SPX 3m = {ret_3m*100:+.1f}%.")
        weights_hit += 0.15

    # Intermarket: stocks vs gold
    if "GC=F" in closes.columns:
        gold = closes["GC=F"].dropna()
        aligned = pd.concat([spx, gold], axis=1, join="inner").dropna()
        if len(aligned) > 80:
            ratio = aligned.iloc[:, 0] / aligned.iloc[:, 1]
            r3 = _last_return(ratio, 63)
            if np.isfinite(r3):
                if r3 > 0.02:
                    score += 0.2
                    reasons.append(f"Ratio SPX/Gold 3m {r3*100:+.1f}% → risk-on intermarket.")
                elif r3 < -0.02:
                    score -= 0.2
                    reasons.append(f"Ratio SPX/Gold 3m {r3*100:+.1f}% → rotación defensiva / risk-off.")
                weights_hit += 0.2

    # Credit / bonds: HYG vs TLT as risk appetite proxy
    if "HYG" in closes.columns and "TLT" in closes.columns:
        hyg = closes["HYG"].dropna()
        tlt = closes["TLT"].dropna()
        aligned = pd.concat([hyg, tlt], axis=1, join="inner").dropna()
        if len(aligned) > 80:
            ratio = aligned.iloc[:, 0] / aligned.iloc[:, 1]
            r3 = _last_return(ratio, 63)
            if np.isfinite(r3):
                if r3 > 0.01:
                    score += 0.15
                    reasons.append(f"HYG/TLT 3m {r3*100:+.1f}% → apetito por crédito (risk-on).")
                elif r3 < -0.01:
                    score -= 0.15
                    reasons.append(f"HYG/TLT 3m {r3*100:+.1f}% → huida a duration (risk-off).")
                weights_hit += 0.15

    # Crypto as speculative risk proxy (optional, lower weight)
    if "BTC-USD" in closes.columns:
        btc = closes["BTC-USD"].dropna()
        r3 = _last_return(btc, 63)
        if np.isfinite(r3):
            if r3 > 0.15:
                score += 0.1
                reasons.append(f"BTC 3m {r3*100:+.1f}% → liquidez especulativa constructiva.")
            elif r3 < -0.15:
                score -= 0.1
                reasons.append(f"BTC 3m {r3*100:+.1f}% → riesgo especulativo en contracción.")
            weights_hit += 0.1

    score = float(np.clip(score, -1.0, 1.0))
    if score >= 0.25:
        label: MacroLabel = "Risk-On"
    elif score <= -0.25:
        label = "Risk-Off"
    else:
        label = "Neutral"

    if not reasons:
        reasons.append("Señales intermarket insuficientes.")

    return label, score, reasons, spx


def rank_stocks(
    universe: list[str],
    spx: pd.Series,
    *,
    top_n: int = 15,
    start: str | None = None,
) -> tuple[list[StockCandidate], float | None, float | None]:
    """Relative strength ranking vs SPX with trend filters."""
    start = start or (date.today() - timedelta(days=420)).isoformat()
    closes = _download_closes(universe, start)
    if closes.empty:
        return [], None, None

    spx = spx.dropna()
    candidates_raw: list[tuple[float, StockCandidate]] = []
    above50 = 0
    above200 = 0
    counted = 0

    for sym in closes.columns:
        px = closes[sym].dropna()
        if len(px) < 220:
            continue
        counted += 1
        sma50 = _sma(px, 50)
        sma200 = _sma(px, 200)
        last = float(px.iloc[-1])
        a50 = bool(np.isfinite(sma50) and last > sma50)
        a200 = bool(np.isfinite(sma200) and last > sma200)
        if a50:
            above50 += 1
        if a200:
            above200 += 1

        # Absolute momentum
        m3 = _last_return(px, 63)
        m6 = _last_return(px, 126)
        m12 = _last_return(px, 252)
        # SPX same windows
        s3 = _last_return(spx, 63)
        s6 = _last_return(spx, 126)
        s12 = _last_return(spx, 252)

        if not all(np.isfinite(x) for x in (m3, m6, m12, s3, s6, s12)):
            continue

        rs3, rs6, rs12 = m3 - s3, m6 - s6, m12 - s12
        # Composite RS score (favor medium-term leadership)
        score = 0.25 * rs3 + 0.45 * rs6 + 0.30 * rs12
        # Bonus for being in uptrend
        if a50 and a200:
            score += 0.03
        elif not a200:
            score -= 0.02

        reasons: list[str] = []
        if rs6 > 0.05:
            reasons.append(f"RS 6m vs SPX {rs6*100:+.1f}% (liderazgo claro).")
        elif rs6 > 0:
            reasons.append(f"RS 6m vs SPX {rs6*100:+.1f}%.")
        else:
            reasons.append(f"RS 6m vs SPX {rs6*100:+.1f}% (rezagado).")
        if a50 and a200:
            reasons.append("Precio > SMA50 y SMA200 (tendencia intacta).")
        elif a200:
            reasons.append("Precio > SMA200 pero débil vs SMA50.")
        else:
            reasons.append("Por debajo de SMA200 (filtro de tendencia fallido).")
        reasons.append(f"Momentum absoluto 6m {m6*100:+.1f}%; 12m {m12*100:+.1f}%.")

        cand = StockCandidate(
            symbol=str(sym),
            rank=0,
            score=round(float(score), 4),
            rs_3m=round(float(rs3), 4),
            rs_6m=round(float(rs6), 4),
            rs_12m=round(float(rs12), 4),
            mom_6m=round(float(m6), 4),
            above_50dma=a50,
            above_200dma=a200,
            reasons=reasons,
        )
        candidates_raw.append((float(score), cand))

    candidates_raw.sort(key=lambda x: x[0], reverse=True)
    ranked: list[StockCandidate] = []
    for i, (_, c) in enumerate(candidates_raw[:top_n], start=1):
        ranked.append(
            StockCandidate(
                symbol=c.symbol,
                rank=i,
                score=c.score,
                rs_3m=c.rs_3m,
                rs_6m=c.rs_6m,
                rs_12m=c.rs_12m,
                mom_6m=c.mom_6m,
                above_50dma=c.above_50dma,
                above_200dma=c.above_200dma,
                reasons=c.reasons,
            )
        )

    b50 = above50 / counted if counted else None
    b200 = above200 / counted if counted else None
    return ranked, b50, b200


def run_alfayate_engine(
    universe: list[str] | None = None,
    *,
    top_n: int = 15,
) -> AlfayateResult:
    """Full top-down pass: macro first, then RS ranking."""
    uni = list(universe) if universe else list(DEFAULT_UNIVERSE)
    macro_label, macro_score, macro_reasons, spx = assess_macro_regime()

    if spx is None or spx.empty:
        return AlfayateResult(
            as_of=date.today().isoformat(),
            macro_label=macro_label,
            macro_score=macro_score,
            macro_reasons=macro_reasons,
            breadth_above_50=None,
            breadth_above_200=None,
            candidates=[],
            universe_size=len(uni),
            notes="No se pudo obtener SPX; ranking omitido.",
        )

    # In Risk-Off, still show ranking but note reduced aggressiveness
    candidates, b50, b200 = rank_stocks(uni, spx, top_n=top_n)

    notes_parts = [
        "Proceso top-down: (1) régimen intermarket/tendencia, (2) ranking RS vs SPX.",
    ]
    if macro_label == "Risk-Off":
        notes_parts.append(
            "Régimen Risk-Off: priorizar defensivas / reducir agresividad aunque el ranking liste líderes relativos."
        )
    elif macro_label == "Risk-On":
        notes_parts.append(
            "Régimen Risk-On: el ranking de líderes de momentum/RS es más actionable en este contexto."
        )
    if b50 is not None:
        notes_parts.append(
            f"Amplitud universo: {b50*100:.0f}% > SMA50; {b200*100:.0f}% > SMA200."
        )

    return AlfayateResult(
        as_of=date.today().isoformat(),
        macro_label=macro_label,
        macro_score=round(macro_score, 4),
        macro_reasons=macro_reasons,
        breadth_above_50=None if b50 is None else round(b50, 4),
        breadth_above_200=None if b200 is None else round(b200, 4),
        candidates=candidates,
        universe_size=len(uni),
        notes=" ".join(notes_parts),
    )
