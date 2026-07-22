"""
Cyclic Index orbital forecast (deterministic, ephemeris-driven).

Projects André Barbault's Cyclic Index forward using the *same* formula as the
historical engine: sum of the 10 minimum pairwise ecliptic arcs among
Jupiter–Saturn–Uranus–Neptune–Pluto.

This is **not** a market prediction. It is pure celestial mechanics.

Kernel policy
-------------
- DE421 covers ~1899-07-29 → 2053-10-09 — insufficient for a full +50y window
  from the mid-2020s (would stop ~2053).
- Forecasts use **JPL DE440s** (`de440s.bsp`) by default, which covers far
  beyond +50 years with high precision for outer planets.
- Historical series may still use DE421; small kernel differences are negligible
  for this index at weekly/monthly sampling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from .cyclic_index import (
    FrameMode,
    compute_cyclic_index,
    compute_cyclic_index_series,
    series_to_dataframe,
)

# Forecast-capable kernel (downloaded on first use into data/ephemeris/)
FORECAST_KERNEL = "de440s.bsp"
# DE421 hard limit (documented for transparency)
DE421_END = date(2053, 10, 9)

DEFAULT_FORECAST_YEARS = 50
DEFAULT_STEP_DAYS = 14  # biweekly: good resolution for 50y charts (~1.3k pts)


@dataclass(frozen=True, slots=True)
class Extremum:
    date: date
    value: float
    kind: Literal["min", "max"]

    def to_dict(self) -> dict:
        return {"date": self.date.isoformat(), "value": self.value, "kind": self.kind}


@dataclass(frozen=True, slots=True)
class ForecastSummary:
    """Lightweight research interpretation of the orbital projection."""

    as_of: date
    end: date
    years: float
    frame: FrameMode
    kernel: str
    current_index: float
    forecast_min: float
    forecast_min_date: date
    forecast_max: float
    forecast_max_date: date
    mean: float
    end_index: float
    slope_per_year: float  # index points / year (OLS on full forecast)
    trend_label: Literal["compresión", "expansión", "lateral"]
    trend_note: str
    next_extrema: list[Extremum] = field(default_factory=list)
    compression_zones: list[dict] = field(default_factory=list)  # low-index windows
    expansion_zones: list[dict] = field(default_factory=list)
    disclaimer: str = (
        "Proyección orbital determinística del Cyclic Index de Barbault a partir de "
        "efemérides JPL. No constituye predicción de mercados ni consejo de inversión."
    )

    def to_dict(self) -> dict:
        return {
            "as_of": self.as_of.isoformat(),
            "end": self.end.isoformat(),
            "years": self.years,
            "frame": self.frame,
            "kernel": self.kernel,
            "current_index": self.current_index,
            "forecast_min": self.forecast_min,
            "forecast_min_date": self.forecast_min_date.isoformat(),
            "forecast_max": self.forecast_max,
            "forecast_max_date": self.forecast_max_date.isoformat(),
            "mean": self.mean,
            "end_index": self.end_index,
            "slope_per_year": self.slope_per_year,
            "trend_label": self.trend_label,
            "trend_note": self.trend_note,
            "next_extrema": [e.to_dict() for e in self.next_extrema],
            "compression_zones": self.compression_zones,
            "expansion_zones": self.expansion_zones,
            "disclaimer": self.disclaimer,
        }


def forecast_end_date(start: date | None = None, years: int = DEFAULT_FORECAST_YEARS) -> date:
    """Calendar end ≈ start + years (using 365.25d approximation via year replace)."""
    start = start or datetime.now(timezone.utc).date()
    try:
        return start.replace(year=start.year + years)
    except ValueError:
        # Feb 29 → Feb 28
        return start.replace(year=start.year + years, day=28)


def compute_cyclic_index_forecast(
    *,
    years: int = DEFAULT_FORECAST_YEARS,
    start: date | str | None = None,
    step_days: int = DEFAULT_STEP_DAYS,
    frame: FrameMode = "heliocentric",
    kernel: str = FORECAST_KERNEL,
) -> pd.DataFrame:
    """
    Build a future Cyclic Index series from `start` (default: today) for `years`.

    Returns a DataFrame with columns matching `series_to_dataframe` plus
    `segment='forecast'`.
    """
    if isinstance(start, str):
        start_d = date.fromisoformat(start)
    elif start is None:
        start_d = datetime.now(timezone.utc).date()
    else:
        start_d = start

    end_d = forecast_end_date(start_d, years=years)
    results = compute_cyclic_index_series(
        start_d,
        end_d,
        step_days=step_days,
        frame=frame,
        kernel=kernel,
    )
    df = series_to_dataframe(results)
    if not df.empty:
        df["segment"] = "forecast"
        df["kernel"] = kernel
    return df


def find_local_extrema(
    series: pd.Series,
    *,
    order: int = 8,
    max_count: int = 6,
) -> list[Extremum]:
    """
    Local minima/maxima on a regularly sampled index series.

    `order` = half-window in samples (e.g. 8 × 14d ≈ 16 weeks).
    Returns extrema sorted by date, capped at `max_count` most extreme of each type
    then re-sorted chronologically (best for 'next relevant' lists).
    """
    s = series.dropna().sort_index()
    if len(s) < order * 2 + 3:
        return []

    vals = s.to_numpy(dtype=float)
    idx = s.index
    mins: list[Extremum] = []
    maxs: list[Extremum] = []

    for i in range(order, len(vals) - order):
        window = vals[i - order : i + order + 1]
        v = vals[i]
        d = pd.Timestamp(idx[i]).date()
        if v == np.min(window) and v < vals[i - 1] and v <= vals[i + 1]:
            mins.append(Extremum(date=d, value=float(v), kind="min"))
        elif v == np.max(window) and v > vals[i - 1] and v >= vals[i + 1]:
            maxs.append(Extremum(date=d, value=float(v), kind="max"))

    # keep strongest extrema
    mins = sorted(mins, key=lambda e: e.value)[: max_count // 2 + 1]
    maxs = sorted(maxs, key=lambda e: e.value, reverse=True)[: max_count // 2 + 1]
    out = sorted(mins + maxs, key=lambda e: e.date)
    return out[:max_count]


def _zone_spans(
    df: pd.DataFrame,
    *,
    low_q: float = 0.25,
    high_q: float = 0.75,
    min_points: int = 4,
) -> tuple[list[dict], list[dict]]:
    """Contiguous spans below low quantile / above high quantile of the forecast."""
    if df.empty:
        return [], []
    y = df["cyclic_index"]
    lo = float(y.quantile(low_q))
    hi = float(y.quantile(high_q))
    dates = pd.to_datetime(df["date"])

    def spans(mask: np.ndarray, label: str, threshold: float) -> list[dict]:
        out: list[dict] = []
        start_i = None
        for i, flag in enumerate(mask):
            if flag and start_i is None:
                start_i = i
            elif not flag and start_i is not None:
                if i - start_i >= min_points:
                    sl = y.iloc[start_i:i]
                    out.append(
                        {
                            "kind": label,
                            "start": dates.iloc[start_i].date().isoformat(),
                            "end": dates.iloc[i - 1].date().isoformat(),
                            "mean_index": round(float(sl.mean()), 2),
                            "threshold": round(threshold, 2),
                        }
                    )
                start_i = None
        if start_i is not None and len(mask) - start_i >= min_points:
            sl = y.iloc[start_i:]
            out.append(
                {
                    "kind": label,
                    "start": dates.iloc[start_i].date().isoformat(),
                    "end": dates.iloc[-1].date().isoformat(),
                    "mean_index": round(float(sl.mean()), 2),
                    "threshold": round(threshold, 2),
                }
            )
        return out

    compression = spans((y <= lo).to_numpy(), "compression", lo)
    expansion = spans((y >= hi).to_numpy(), "expansion", hi)
    return compression, expansion


def summarize_forecast(
    forecast_df: pd.DataFrame,
    *,
    frame: FrameMode = "heliocentric",
    kernel: str = FORECAST_KERNEL,
    step_days: int = DEFAULT_STEP_DAYS,
) -> ForecastSummary:
    """Build KPIs + light research interpretation from a forecast DataFrame."""
    if forecast_df.empty:
        raise ValueError("Empty forecast series")

    df = forecast_df.sort_values("date").reset_index(drop=True)
    as_of = pd.Timestamp(df["date"].iloc[0]).date()
    end = pd.Timestamp(df["date"].iloc[-1]).date()
    years = (end - as_of).days / 365.25
    y = df["cyclic_index"].to_numpy(dtype=float)

    current = float(y[0])
    end_v = float(y[-1])
    imin = int(np.argmin(y))
    imax = int(np.argmax(y))
    fmin = float(y[imin])
    fmax = float(y[imax])
    dmin = pd.Timestamp(df["date"].iloc[imin]).date()
    dmax = pd.Timestamp(df["date"].iloc[imax]).date()
    mean = float(np.mean(y))

    # OLS slope in points / year
    x = np.arange(len(y), dtype=float)
    if len(y) >= 3:
        coef = np.polyfit(x, y, 1)
        slope_per_step = float(coef[0])
        steps_per_year = 365.25 / step_days
        slope_yr = slope_per_step * steps_per_year
    else:
        slope_yr = 0.0

    if slope_yr <= -2.0:
        trend: Literal["compresión", "expansión", "lateral"] = "compresión"
        trend_note = (
            f"Pendiente proyectada ≈ {slope_yr:+.1f}°/año: el índice tiende a **bajar** "
            f"(menor dispersión angular media de planetas lentos → compresión cíclica)."
        )
    elif slope_yr >= 2.0:
        trend = "expansión"
        trend_note = (
            f"Pendiente proyectada ≈ {slope_yr:+.1f}°/año: el índice tiende a **subir** "
            f"(mayor dispersión angular → expansión cíclica)."
        )
    else:
        trend = "lateral"
        trend_note = (
            f"Pendiente proyectada ≈ {slope_yr:+.1f}°/año: evolución **sin sesgo fuerte** "
            f"de compresión/expansión a escala multi-década."
        )

    s = df.set_index(pd.to_datetime(df["date"]))["cyclic_index"]
    extrema = find_local_extrema(s, order=max(4, int(round(90 / step_days))), max_count=6)
    # prefer upcoming extrema after first sample
    next_ext = [e for e in extrema if e.date > as_of][:5]
    if not next_ext:
        next_ext = extrema[:4]

    compression, expansion = _zone_spans(df)

    return ForecastSummary(
        as_of=as_of,
        end=end,
        years=round(years, 2),
        frame=frame,
        kernel=kernel,
        current_index=round(current, 4),
        forecast_min=round(fmin, 4),
        forecast_min_date=dmin,
        forecast_max=round(fmax, 4),
        forecast_max_date=dmax,
        mean=round(mean, 4),
        end_index=round(end_v, 4),
        slope_per_year=round(slope_yr, 3),
        trend_label=trend,
        trend_note=trend_note,
        next_extrema=next_ext,
        compression_zones=compression[:5],
        expansion_zones=expansion[:5],
    )


def forecast_csv_path(
    frame: FrameMode = "heliocentric",
    years: int = DEFAULT_FORECAST_YEARS,
    generated_dir: Path | None = None,
) -> Path:
    root = generated_dir or Path(__file__).resolve().parents[3] / "data" / "generated"
    return root / f"cyclic_index_forecast_{years}y_{frame}.csv"


def load_or_build_forecast(
    *,
    years: int = DEFAULT_FORECAST_YEARS,
    step_days: int = DEFAULT_STEP_DAYS,
    frame: FrameMode = "heliocentric",
    kernel: str = FORECAST_KERNEL,
    force_rebuild: bool = False,
    generated_dir: Path | None = None,
) -> tuple[pd.DataFrame, ForecastSummary]:
    """
    Load cached forecast CSV or recompute. Rebuilds if:
    - missing / force_rebuild
    - first date is more than `step_days` behind today (stale start)
    """
    path = forecast_csv_path(frame=frame, years=years, generated_dir=generated_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date()

    if path.exists() and not force_rebuild:
        df = pd.read_csv(path, parse_dates=["date"])
        if not df.empty:
            first = pd.Timestamp(df["date"].min()).date()
            last = pd.Timestamp(df["date"].max()).date()
            expected_end = forecast_end_date(today, years=years)
            # Accept cache if it starts near today and ends near +years
            start_ok = abs((first - today).days) <= max(step_days * 2, 21)
            end_ok = last >= expected_end - timedelta(days=step_days * 3)
            if start_ok and end_ok:
                summary = summarize_forecast(df, frame=frame, kernel=kernel, step_days=step_days)
                return df, summary

    df = compute_cyclic_index_forecast(
        years=years,
        start=today,
        step_days=step_days,
        frame=frame,
        kernel=kernel,
    )
    df.to_csv(path, index=False)
    summary = summarize_forecast(df, frame=frame, kernel=kernel, step_days=step_days)
    return df, summary


def kernel_coverage_note() -> str:
    return (
        f"**DE421** solo cubre hasta ~{DE421_END.isoformat()} "
        f"(insuficiente para +50 años desde 2026+). "
        f"El forecast usa **{FORECAST_KERNEL} (JPL DE440s)**, válido bien más allá de 2076. "
        f"La fórmula del índice es idéntica; solo cambia el kernel de efemérides."
    )
