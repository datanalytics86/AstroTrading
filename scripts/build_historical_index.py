#!/usr/bin/env python3
"""
Build historical Cyclic Index series and persist to data/generated/.

Usage:
  python scripts/build_historical_index.py
  python scripts/build_historical_index.py --start 1990-01-01 --step 7
  python scripts/build_historical_index.py --frame geocentric
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from astrotrading.astrology.cyclic_index import (  # noqa: E402
    compute_cyclic_index_series,
    series_to_dataframe,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Barbault Cyclic Index history")
    parser.add_argument("--start", default="2000-01-01")
    parser.add_argument("--end", default=None, help="ISO date (default: today UTC)")
    parser.add_argument("--step", type=int, default=7, help="Sampling step in days")
    parser.add_argument(
        "--frame",
        choices=["heliocentric", "geocentric"],
        default="heliocentric",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output CSV path (default: data/generated/cyclic_index_<frame>.csv)",
    )
    args = parser.parse_args()

    end = args.end or date.today().isoformat()
    out = Path(args.out) if args.out else ROOT / "data" / "generated" / f"cyclic_index_{args.frame}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"Computing Cyclic Index [{args.frame}] {args.start} → {end} (step={args.step}d)…")
    results = compute_cyclic_index_series(
        args.start,
        end,
        step_days=args.step,
        frame=args.frame,
    )
    df = series_to_dataframe(results)
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} rows → {out}")
    if not df.empty:
        print(
            f"  range: {df['cyclic_index'].min():.2f} – {df['cyclic_index'].max():.2f} "
            f"(mean {df['cyclic_index'].mean():.2f})"
        )
        print(f"  last:  {df.iloc[-1]['date'].date()} = {df.iloc[-1]['cyclic_index']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
