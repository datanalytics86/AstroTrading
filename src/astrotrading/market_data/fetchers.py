"""
Market data layer — yfinance primary, easy extension points for Polygon etc.

Default universe for Astro Quant comparisons:
  - S&P 500 (^GSPC)
  - Gold (GC=F or GLD)
  - Bitcoin (BTC-USD)
  - WTI Crude Oil (CL=F)
  - Copper (HG=F)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True, slots=True)
class AssetSpec:
    key: str
    label: str
    yfinance_ticker: str
    asset_class: str  # equity_index | metal | crypto | energy | industrial_metal


# Ordered universe — append new AssetSpec rows to extend charts easily.
ASSET_UNIVERSE: tuple[AssetSpec, ...] = (
    AssetSpec("spx", "S&P 500", "^GSPC", "equity_index"),
    AssetSpec("gold", "Gold", "GC=F", "metal"),
    AssetSpec("btc", "Bitcoin", "BTC-USD", "crypto"),
    AssetSpec("wti", "WTI Crude Oil", "CL=F", "energy"),
    AssetSpec("copper", "Copper", "HG=F", "industrial_metal"),
)

# Fallback tickers if primary fails (e.g. futures offline)
_FALLBACKS: dict[str, list[str]] = {
    "gold": ["GLD", "IAU"],
    "wti": ["USO", "CL=F"],
    "copper": ["CPER", "HG=F"],
}


def _cache_path(ticker: str, start: str, end: str) -> Path:
    safe = ticker.replace("=", "_").replace("^", "")
    return CACHE_DIR / f"{safe}_{start}_{end}.parquet"


def fetch_price_history(
    ticker: str,
    start: date | str,
    end: date | str | None = None,
    *,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Daily OHLCV for a single ticker via yfinance.

    Returns DataFrame indexed by date with columns:
      open, high, low, close, adj_close, volume
    """
    import yfinance as yf

    if isinstance(start, date):
        start_s = start.isoformat()
    else:
        start_s = start
    if end is None:
        end_s = date.today().isoformat()
    elif isinstance(end, date):
        end_s = end.isoformat()
    else:
        end_s = end

    cache = _cache_path(ticker, start_s, end_s)
    if use_cache and cache.exists():
        # Refresh if cache older than 1 day
        mtime = datetime.fromtimestamp(cache.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=18):
            try:
                df = pd.read_parquet(cache)
                if not df.empty:
                    return df
            except Exception:
                pass

    logger.info("Downloading %s [%s → %s]", ticker, start_s, end_s)
    raw = yf.download(
        ticker,
        start=start_s,
        end=end_s,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if raw is None or raw.empty:
        return pd.DataFrame()

    # yfinance multi-index columns when single ticker sometimes still nested
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0].lower().replace(" ", "_") for c in raw.columns]
    else:
        raw.columns = [str(c).lower().replace(" ", "_") for c in raw.columns]

    rename = {"adj close": "adj_close"}
    raw = raw.rename(columns=rename)
    raw.index = pd.to_datetime(raw.index).tz_localize(None)
    raw.index.name = "date"
    out = raw.reset_index()

    if use_cache and not out.empty:
        try:
            out.to_parquet(cache, index=False)
        except Exception as exc:
            logger.debug("Cache write failed: %s", exc)

    return out


def fetch_multi_asset(
    start: date | str = "2000-01-01",
    end: date | str | None = None,
    assets: Iterable[AssetSpec] | None = None,
    *,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Wide panel of adjusted closes: columns = asset keys, index = date.

    Tries fallback tickers if primary series is empty.
    """
    specs = list(assets) if assets is not None else list(ASSET_UNIVERSE)
    frames: dict[str, pd.Series] = {}

    for spec in specs:
        tickers = [spec.yfinance_ticker] + _FALLBACKS.get(spec.key, [])
        series = None
        for tkr in tickers:
            df = fetch_price_history(tkr, start, end, use_cache=use_cache)
            if df.empty:
                continue
            price_col = "adj_close" if "adj_close" in df.columns else "close"
            if price_col not in df.columns:
                continue
            s = df.set_index("date")[price_col].astype(float)
            s = s[~s.index.duplicated(keep="last")].sort_index()
            if len(s.dropna()) > 10:
                series = s
                logger.info("Using ticker %s for %s", tkr, spec.key)
                break
        if series is not None:
            frames[spec.key] = series
        else:
            logger.warning("No data for asset %s", spec.key)

    if not frames:
        return pd.DataFrame()

    panel = pd.DataFrame(frames).sort_index()
    panel.index = pd.to_datetime(panel.index)
    return panel


def normalize_rebased(panel: pd.DataFrame, base: float = 100.0) -> pd.DataFrame:
    """Rebase each column to `base` at first valid observation."""
    out = panel.copy()
    for col in out.columns:
        s = out[col].dropna()
        if s.empty:
            continue
        first = s.iloc[0]
        if first and first != 0:
            out[col] = out[col] / first * base
    return out


def daily_returns(panel: pd.DataFrame) -> pd.DataFrame:
    return panel.pct_change()
