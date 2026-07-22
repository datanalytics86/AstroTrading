"""
Cyclic Index of André Barbault — exact deterministic implementation.

Formula (mandatory):
  1. Take ecliptic longitudes of Jupiter, Saturn, Uranus, Neptune, Pluto.
  2. Compute the 10 shortest angular distances (minimum arc ≤ 180°) between all pairs.
  3. Sum those 10 distances → Cyclic Index (degrees).

Reference frame:
  - heliocentric (classic Barbault) — primary
  - geocentric — optional secondary

Ephemeris: JPL DE421/DE440 via skyfield + jplephem (high precision, deterministic).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from functools import lru_cache
from itertools import combinations
from pathlib import Path
from typing import Iterable, Literal, Sequence

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLANETS: tuple[str, ...] = (
    "jupiter",
    "saturn",
    "uranus",
    "neptune",
    "pluto",
)

# skyfield / JPL body keys (barycenters are the standard high-quality choice
# for outer planets in DE ephemerides)
_BODY_KEYS: dict[str, str] = {
    "jupiter": "jupiter barycenter",
    "saturn": "saturn barycenter",
    "uranus": "uranus barycenter",
    "neptune": "neptune barycenter",
    "pluto": "pluto barycenter",
}

FrameMode = Literal["heliocentric", "geocentric"]

# Default kernel location (downloaded once by skyfield)
_DEFAULT_KERNEL = "de421.bsp"


# ---------------------------------------------------------------------------
# Pure math (no ephemeris dependency — fully unit-testable)
# ---------------------------------------------------------------------------


def angular_separation(lon_a: float, lon_b: float) -> float:
    """
    Shortest angular distance on the circle between two ecliptic longitudes.

    Both inputs in degrees (any real number). Result in [0, 180].
    """
    diff = abs(lon_a - lon_b) % 360.0
    return min(diff, 360.0 - diff)


def pair_distances(longitudes: Sequence[float]) -> list[tuple[tuple[str, str], float]]:
    """
    All C(n,2) pairwise shortest angular distances.

    For the five outer planets this yields exactly 10 pairs.
    Returns list of ((name_a, name_b), distance_deg) sorted by pair names.
    """
    if len(longitudes) != len(PLANETS):
        raise ValueError(
            f"Expected {len(PLANETS)} longitudes (one per outer planet), got {len(longitudes)}"
        )
    pairs: list[tuple[tuple[str, str], float]] = []
    for (i, name_a), (j, name_b) in combinations(enumerate(PLANETS), 2):
        d = angular_separation(float(longitudes[i]), float(longitudes[j]))
        pairs.append(((name_a, name_b), d))
    return pairs


def cyclic_index_from_longitudes(longitudes: Sequence[float]) -> float:
    """
    Cyclic Index from a sequence of 5 ecliptic longitudes (degrees).

    Sum of the 10 shortest pairwise angular distances.
    Pure function — no I/O, fully deterministic.
    """
    pairs = pair_distances(longitudes)
    return float(sum(d for _, d in pairs))


# ---------------------------------------------------------------------------
# Ephemeris loading (cached)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4)
def _load_ephemeris(kernel: str = _DEFAULT_KERNEL):
    """Load JPL ephemeris kernel via skyfield (cached).

    Supported kernels in this project:
      - de421.bsp  — historical default (~1900–2053)
      - de440s.bsp — forecast / long-horizon (covers +50y and beyond)
    """
    from skyfield.api import Loader

    # Prefer project data/ dir so kernels are versionable / offline-friendly
    data_dir = Path(__file__).resolve().parents[3] / "data" / "ephemeris"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Streamlit Cloud / read-only edge: Loader may still read if kernel exists
        pass
    loader = Loader(str(data_dir))
    return loader(kernel), loader.timescale()


def _as_utc_datetime(when: date | datetime) -> datetime:
    if isinstance(when, datetime):
        if when.tzinfo is None:
            return when.replace(tzinfo=timezone.utc)
        return when.astimezone(timezone.utc)
    # date → noon UTC (standard convention for daily index)
    return datetime(when.year, when.month, when.day, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Longitude extraction
# ---------------------------------------------------------------------------


def ecliptic_longitudes(
    when: date | datetime,
    *,
    frame: FrameMode = "heliocentric",
    kernel: str = _DEFAULT_KERNEL,
) -> dict[str, float]:
    """
    Ecliptic longitudes (degrees, [0, 360)) for the five outer planets.

    Parameters
    ----------
    when : date or datetime
        Observation time. bare `date` uses 12:00 UTC.
    frame : 'heliocentric' | 'geocentric'
        Reference origin (Sun vs Earth).
    kernel : str
        JPL SPICE kernel name (default de421.bsp).
    """
    from skyfield.framelib import ecliptic_frame

    eph, ts = _load_ephemeris(kernel)
    dt = _as_utc_datetime(when)
    t = ts.utc(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)

    if frame == "heliocentric":
        origin = eph["sun"]
    elif frame == "geocentric":
        origin = eph["earth"]
    else:
        raise ValueError(f"Unknown frame: {frame!r}")

    result: dict[str, float] = {}
    for name in PLANETS:
        body = eph[_BODY_KEYS[name]]
        # apparent() accounts for light-time / aberration — preferred for geocentric;
        # for heliocentric geometric is closer to classical tabular practice, but
        # apparent is still high-precision and consistent. We use geometric for
        # heliocentric (no light-time from Sun center) and apparent for geocentric.
        if frame == "heliocentric":
            astrometric = origin.at(t).observe(body)
        else:
            astrometric = origin.at(t).observe(body).apparent()
        lat, lon, _dist = astrometric.frame_latlon(ecliptic_frame)
        # normalize to [0, 360)
        result[name] = float(lon.degrees % 360.0)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CyclicIndexResult:
    """Full deterministic result for a single date."""

    date: date
    index: float
    frame: FrameMode
    longitudes: dict[str, float]
    pairs: dict[str, float]  # "jupiter-saturn" → distance deg

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "index": self.index,
            "frame": self.frame,
            "longitudes": self.longitudes,
            "pairs": self.pairs,
        }


def compute_cyclic_index(
    when: date | datetime | str,
    *,
    frame: FrameMode = "heliocentric",
    kernel: str = _DEFAULT_KERNEL,
) -> CyclicIndexResult:
    """
    Compute André Barbault's Cyclic Index for a given date.

    Parameters
    ----------
    when : date | datetime | str
        Target date. ISO string 'YYYY-MM-DD' accepted.
    frame : 'heliocentric' (default, classic Barbault) | 'geocentric'
    kernel : JPL kernel filename

    Returns
    -------
    CyclicIndexResult with index in degrees (theoretical range ~0–1800,
    practical historical range typically ~400–1200 depending on era).
    """
    if isinstance(when, str):
        when = date.fromisoformat(when)

    longs = ecliptic_longitudes(when, frame=frame, kernel=kernel)
    ordered = [longs[p] for p in PLANETS]
    pairs_list = pair_distances(ordered)
    index = float(sum(d for _, d in pairs_list))

    pair_map = {f"{a}-{b}": d for (a, b), d in pairs_list}
    d = when if isinstance(when, date) and not isinstance(when, datetime) else _as_utc_datetime(when).date()

    return CyclicIndexResult(
        date=d,
        index=index,
        frame=frame,
        longitudes=longs,
        pairs=pair_map,
    )


def compute_cyclic_index_series(
    start: date | str,
    end: date | str,
    *,
    step_days: int = 7,
    frame: FrameMode = "heliocentric",
    kernel: str = _DEFAULT_KERNEL,
) -> list[CyclicIndexResult]:
    """
    Compute Cyclic Index over a date range (inclusive).

    step_days=7 is a good default for multi-decade charts (weekly samples).
    """
    if isinstance(start, str):
        start = date.fromisoformat(start)
    if isinstance(end, str):
        end = date.fromisoformat(end)
    if step_days < 1:
        raise ValueError("step_days must be >= 1")
    if end < start:
        raise ValueError("end must be >= start")

    from datetime import timedelta

    results: list[CyclicIndexResult] = []
    current = start
    delta = timedelta(days=step_days)
    while current <= end:
        results.append(compute_cyclic_index(current, frame=frame, kernel=kernel))
        current = current + delta
    # ensure end date is included if step skipped it
    if results and results[-1].date != end:
        results.append(compute_cyclic_index(end, frame=frame, kernel=kernel))
    return results


def series_to_dataframe(
    results: Iterable[CyclicIndexResult],
):
    """Convert a list of CyclicIndexResult into a pandas DataFrame."""
    import pandas as pd

    rows = [
        {
            "date": r.date,
            "cyclic_index": r.index,
            "frame": r.frame,
            **{f"lon_{k}": v for k, v in r.longitudes.items()},
        }
        for r in results
    ]
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Vectorized helpers for testing edge cases
# ---------------------------------------------------------------------------


def _angular_separation_vectorized(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Vectorized shortest arc; same definition as angular_separation."""
    diff = np.abs(a - b) % 360.0
    return np.minimum(diff, 360.0 - diff)


def validate_index_bounds(index: float) -> bool:
    """
    Theoretical bounds: each of 10 pairs ∈ [0, 180] → index ∈ [0, 1800].
    Returns True if within bounds (with tiny float tolerance).
    """
    return -1e-9 <= index <= 1800.0 + 1e-9
