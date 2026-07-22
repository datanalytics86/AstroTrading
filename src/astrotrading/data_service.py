"""
Cached data loading for the dashboard.

Loads / builds Cyclic Index history, market panels, regime, comparisons.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd

from astrotrading.astrology.cyclic_index import (
    compute_cyclic_index,
    compute_cyclic_index_series,
    series_to_dataframe,
)
from astrotrading.market_data.fetchers import ASSET_UNIVERSE, fetch_multi_asset
from astrotrading.quant.comparison import compare_index_vs_assets
from astrotrading.quant.regime import RegimeSignal, classify_regime

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "data" / "generated"
GENERATED.mkdir(parents=True, exist_ok=True)


def cyclic_csv_path(frame: str = "heliocentric") -> Path:
    return GENERATED / f"cyclic_index_{frame}.csv"


def load_or_build_cyclic_series(
    *,
    start: str = "2000-01-01",
    step_days: int = 7,
    frame: str = "heliocentric",
    force_rebuild: bool = False,
) -> pd.DataFrame:
    """
    Load CSV cache or compute full series. Updates with missing tail up to today.
    """
    path = cyclic_csv_path(frame)
    end = date.today()

    if path.exists() and not force_rebuild:
        df = pd.read_csv(path, parse_dates=["date"])
        if not df.empty:
            last = pd.Timestamp(df["date"].max()).date()
            if last < end:
                # append missing weeks
                from datetime import timedelta

                resume = last + timedelta(days=step_days)
                if resume <= end:
                    logger.info("Updating cyclic series from %s", resume)
                    extra = compute_cyclic_index_series(
                        resume, end, step_days=step_days, frame=frame  # type: ignore[arg-type]
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
            return df

    logger.info("Building full cyclic series %s → %s", start, end)
    results = compute_cyclic_index_series(start, end, step_days=step_days, frame=frame)  # type: ignore[arg-type]
    df = series_to_dataframe(results)
    df.to_csv(path, index=False)
    return df


def current_index(frame: str = "heliocentric"):
    return compute_cyclic_index(date.today(), frame=frame)  # type: ignore[arg-type]


def load_market_panel(start: str = "2000-01-01") -> pd.DataFrame:
    return fetch_multi_asset(start=start)


def build_regime(cyclic_df: pd.DataFrame, step_days: int = 7) -> RegimeSignal:
    s = cyclic_df.set_index("date")["cyclic_index"].sort_index()
    return classify_regime(s, step_days=step_days)


def build_comparison(cyclic_df: pd.DataFrame, market: pd.DataFrame) -> dict:
    s = cyclic_df.set_index("date")["cyclic_index"].sort_index()
    return compare_index_vs_assets(s, market)


def asset_labels() -> dict[str, str]:
    return {a.key: a.label for a in ASSET_UNIVERSE}
