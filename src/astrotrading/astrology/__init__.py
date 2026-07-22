"""Astrological / celestial mechanics engines.

Keep this package init lightweight: only export the core Cyclic Index API.
Forecast helpers live in `astrotrading.astrology.forecast` and should be
imported from there (avoids heavy/circular imports on Streamlit Cloud).
"""

from .cyclic_index import (
    PLANETS,
    angular_separation,
    compute_cyclic_index,
    compute_cyclic_index_series,
    pair_distances,
)

__all__ = [
    "PLANETS",
    "angular_separation",
    "compute_cyclic_index",
    "compute_cyclic_index_series",
    "pair_distances",
]
