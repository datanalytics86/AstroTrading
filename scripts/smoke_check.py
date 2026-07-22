#!/usr/bin/env python3
"""Quick smoke check: cyclic index today + optional market tick."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    from astrotrading.astrology import compute_cyclic_index

    r = compute_cyclic_index(date.today(), frame="heliocentric")
    print(f"OK  Cyclic Index {r.date} = {r.index:.4f}° ({r.frame})")
    for p, lon in r.longitudes.items():
        print(f"    {p:8s}  λ = {lon:8.4f}°")
    print(f"    pairs sum check = {sum(r.pairs.values()):.4f}")

    for anchor in ("1920-01-01", "2000-01-01"):
        r2 = compute_cyclic_index(anchor)
        print(f"OK  Anchor {anchor} = {r2.index:.4f}°")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
