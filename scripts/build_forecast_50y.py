#!/usr/bin/env python3
"""
Build / refresh the 50-year Cyclic Index orbital forecast.

Uses JPL DE440s (DE421 ends ~2053 — insufficient for +50y from mid-2020s).

Usage:
  python scripts/build_forecast_50y.py
  python scripts/build_forecast_50y.py --years 50 --step 14 --frame heliocentric
  python scripts/build_forecast_50y.py --force
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from astrotrading.astrology.forecast import (  # noqa: E402
    FORECAST_KERNEL,
    kernel_coverage_note,
    load_or_build_forecast,
)


def main() -> int:
    p = argparse.ArgumentParser(description="Build 50y Cyclic Index forecast")
    p.add_argument("--years", type=int, default=50)
    p.add_argument("--step", type=int, default=14, help="Sampling step in days")
    p.add_argument("--frame", choices=["heliocentric", "geocentric"], default="heliocentric")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    print(kernel_coverage_note())
    print(f"\nBuilding forecast: {args.years}y · step={args.step}d · {args.frame} · kernel={FORECAST_KERNEL}")
    df, summary = load_or_build_forecast(
        years=args.years,
        step_days=args.step,
        frame=args.frame,  # type: ignore[arg-type]
        force_rebuild=args.force,
        generated_dir=ROOT / "data" / "generated",
    )
    print(f"Rows: {len(df)}")
    print(
        f"Range: {summary.as_of} → {summary.end} | "
        f"now={summary.current_index:.2f}° | "
        f"min={summary.forecast_min:.2f}° ({summary.forecast_min_date}) | "
        f"max={summary.forecast_max:.2f}° ({summary.forecast_max_date})"
    )
    print(f"Trend: {summary.trend_label} ({summary.slope_per_year:+.2f}°/yr)")
    for e in summary.next_extrema[:5]:
        print(f"  extremum {e.kind}: {e.date} = {e.value:.2f}°")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
