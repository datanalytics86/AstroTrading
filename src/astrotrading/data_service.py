"""
Cached data loading for the dashboard.

Loads / builds Cyclic Index history, market panels, regime, comparisons.

Default history window: 1920 → today (weekly), for long-horizon correlation work.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from astrotrading.astrology.cyclic_index import (
    compute_cyclic_index,
    compute_cyclic_index_series,
    series_to_dataframe,
)
from astrotrading.astrology.forecast import (
    DEFAULT_FORECAST_YEARS,
    FORECAST_KERNEL,
    ForecastSummary,
    load_or_build_forecast,
)
from astrotrading.market_data.fetchers import ASSET_UNIVERSE, fetch_multi_asset
from astrotrading.quant.comparison import compare_index_vs_assets
from astrotrading.quant.regime import RegimeSignal, classify_regime

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "data" / "generated"
GENERATED.mkdir(parents=True, exist_ok=True)

# Longest default window (JPL DE421 covers ~1900–2050)
DEFAULT_INDEX_START = "1920-01-01"
DEFAULT_STEP_DAYS = 7


def cyclic_csv_path(frame: str = "heliocentric") -> Path:
    return GENERATED / f"cyclic_index_{frame}.csv"


def load_or_build_cyclic_series(
    *,
    start: str = DEFAULT_INDEX_START,
    step_days: int = DEFAULT_STEP_DAYS,
    frame: str = "heliocentric",
    force_rebuild: bool = False,
    clip_to_start: bool = True,
) -> pd.DataFrame:
    """
    Load CSV cache or compute full series.

    - Extends **forward** to today if the cache is stale.
    - Extends **backward** if the requested `start` is earlier than the cache min date.
    - By default returns rows with date >= `start` (full cache is still persisted).
    """
    path = cyclic_csv_path(frame)
    end = date.today()
    start_d = date.fromisoformat(start) if isinstance(start, str) else start

    if path.exists() and not force_rebuild:
        df = pd.read_csv(path, parse_dates=["date"])
        if not df.empty:
            first = pd.Timestamp(df["date"].min()).date()
            last = pd.Timestamp(df["date"].max()).date()

            # --- prepend missing history ---
            if start_d < first:
                logger.info("Extending cyclic series backward %s → %s", start_d, first)
                # stop one step before existing first to avoid duplicate
                back_end = first - timedelta(days=1)
                if start_d <= back_end:
                    extra = compute_cyclic_index_series(
                        start_d,
                        back_end,
                        step_days=step_days,
                        frame=frame,  # type: ignore[arg-type]
                    )
                    if extra:
                        extra_df = series_to_dataframe(extra)
                        df = (
                            pd.concat([extra_df, df], ignore_index=True)
                            .drop_duplicates(subset=["date"], keep="last")
                            .sort_values("date")
                            .reset_index(drop=True)
                        )
                        df.to_csv(path, index=False)
                        first = pd.Timestamp(df["date"].min()).date()

            # --- append missing tail ---
            if last < end:
                resume = last + timedelta(days=step_days)
                if resume <= end:
                    logger.info("Updating cyclic series forward from %s", resume)
                    extra = compute_cyclic_index_series(
                        resume,
                        end,
                        step_days=step_days,
                        frame=frame,  # type: ignore[arg-type]
                    )
                    if extra:
                        extra_df = series_to_dataframe(extra)
                        df = (
                            pd.concat([df, extra_df], ignore_index=True)
                            .drop_duplicates(subset=["date"], keep="last")
                            .sort_values("date")
                            .reset_index(drop=True)
                        )
                        df.to_csv(path, index=False)

            if clip_to_start:
                df = df[df["date"] >= pd.Timestamp(start_d)].reset_index(drop=True)
            return df

    logger.info("Building full cyclic series %s → %s", start_d, end)
    results = compute_cyclic_index_series(
        start_d, end, step_days=step_days, frame=frame  # type: ignore[arg-type]
    )
    df = series_to_dataframe(results)
    df.to_csv(path, index=False)
    if clip_to_start:
        df = df[df["date"] >= pd.Timestamp(start_d)].reset_index(drop=True)
    return df


def current_index(frame: str = "heliocentric"):
    return compute_cyclic_index(date.today(), frame=frame)  # type: ignore[arg-type]


def load_market_panel(start: str = DEFAULT_INDEX_START) -> pd.DataFrame:
    """
    Multi-asset panel from `start`.

    Note: not all assets exist back to 1920 (e.g. BTC ~2014, many futures later).
    SPX (^GSPC) via yfinance typically reaches ~1927. Alignment is inner/outer
    as handled by the comparison module.
    """
    return fetch_multi_asset(start=start)


def build_regime(cyclic_df: pd.DataFrame, step_days: int = DEFAULT_STEP_DAYS) -> RegimeSignal:
    s = cyclic_df.set_index("date")["cyclic_index"].sort_index()
    return classify_regime(s, step_days=step_days)


def build_comparison(cyclic_df: pd.DataFrame, market: pd.DataFrame) -> dict:
    s = cyclic_df.set_index("date")["cyclic_index"].sort_index()
    return compare_index_vs_assets(s, market)


def asset_labels() -> dict[str, str]:
    return {a.key: a.label for a in ASSET_UNIVERSE}


def load_forecast(
    *,
    years: int = DEFAULT_FORECAST_YEARS,
    step_days: int = 14,
    frame: str = "heliocentric",
    force_rebuild: bool = False,
) -> tuple[pd.DataFrame, ForecastSummary]:
    """
    50-year (default) orbital forecast of the Cyclic Index.

    Uses JPL DE440s — DE421 stops ~2053 and cannot cover a full +50y window.
    """
    return load_or_build_forecast(
        years=years,
        step_days=step_days,
        frame=frame,  # type: ignore[arg-type]
        kernel=FORECAST_KERNEL,
        force_rebuild=force_rebuild,
        generated_dir=GENERATED,
    )
