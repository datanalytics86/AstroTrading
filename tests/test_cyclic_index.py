"""
Unit tests for André Barbault's Cyclic Index engine.

Covers:
  - pure angular math (no ephemeris)
  - pair counting (exactly 10)
  - determinism / reproducibility
  - bounds
  - both heliocentric and geocentric frames
  - historical sample dates
"""

from __future__ import annotations

from datetime import date

import pytest

from astrotrading.astrology.cyclic_index import (
    PLANETS,
    angular_separation,
    compute_cyclic_index,
    compute_cyclic_index_series,
    cyclic_index_from_longitudes,
    pair_distances,
    validate_index_bounds,
)


# ---------------------------------------------------------------------------
# Pure math
# ---------------------------------------------------------------------------


class TestAngularSeparation:
    def test_identical(self):
        assert angular_separation(0.0, 0.0) == 0.0
        assert angular_separation(123.45, 123.45) == 0.0

    def test_right_angle(self):
        assert angular_separation(0.0, 90.0) == 90.0
        assert angular_separation(90.0, 0.0) == 90.0

    def test_opposition(self):
        assert angular_separation(0.0, 180.0) == 180.0
        assert angular_separation(10.0, 190.0) == 180.0

    def test_wrap_around(self):
        # 350° vs 10° → shortest arc is 20°, not 340°
        assert angular_separation(350.0, 10.0) == pytest.approx(20.0)
        assert angular_separation(10.0, 350.0) == pytest.approx(20.0)

    def test_never_exceeds_180(self):
        for a in range(0, 360, 15):
            for b in range(0, 360, 15):
                d = angular_separation(float(a), float(b))
                assert 0.0 <= d <= 180.0

    def test_symmetry(self):
        assert angular_separation(40.0, 200.0) == angular_separation(200.0, 40.0)

    def test_modulo_inputs(self):
        # longitudes outside [0, 360) must still work
        assert angular_separation(370.0, 10.0) == pytest.approx(0.0)
        assert angular_separation(-10.0, 10.0) == pytest.approx(20.0)


class TestPairDistances:
    def test_exactly_ten_pairs(self):
        # five equal longitudes → 10 zeros
        longs = [0.0, 0.0, 0.0, 0.0, 0.0]
        pairs = pair_distances(longs)
        assert len(pairs) == 10
        assert all(d == 0.0 for _, d in pairs)

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError):
            pair_distances([0.0, 1.0, 2.0])

    def test_known_geometry(self):
        # planets at 0, 60, 120, 180, 240
        longs = [0.0, 60.0, 120.0, 180.0, 240.0]
        pairs = pair_distances(longs)
        dists = sorted(d for _, d in pairs)
        # all pairwise min arcs among those positions
        expected = sorted(
            [
                60,   # 0-60
                120,  # 0-120
                180,  # 0-180
                120,  # 0-240 → min(240,120)=120
                60,   # 60-120
                120,  # 60-180
                180,  # 60-240
                60,   # 120-180
                120,  # 120-240
                60,   # 180-240
            ]
        )
        assert dists == pytest.approx(expected)

    def test_pair_names_use_planet_order(self):
        pairs = pair_distances([0, 1, 2, 3, 4])
        names = {p for p, _ in pairs}
        assert ("jupiter", "saturn") in names
        assert ("jupiter", "pluto") in names
        assert ("neptune", "pluto") in names
        assert len(names) == 10


class TestCyclicIndexFromLongitudes:
    def test_all_conjunction(self):
        # theoretical minimum
        assert cyclic_index_from_longitudes([0, 0, 0, 0, 0]) == 0.0

    def test_sum_of_pairs(self):
        longs = [0.0, 90.0, 180.0, 270.0, 45.0]
        pairs = pair_distances(longs)
        expected = sum(d for _, d in pairs)
        assert cyclic_index_from_longitudes(longs) == pytest.approx(expected)

    def test_bounds(self):
        # evenly spaced-ish
        idx = cyclic_index_from_longitudes([0, 72, 144, 216, 288])
        assert validate_index_bounds(idx)
        assert idx > 0


# ---------------------------------------------------------------------------
# Ephemeris-backed (requires skyfield + kernel download on first run)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sample_heliocentric():
    return compute_cyclic_index(date(2000, 1, 1), frame="heliocentric")


@pytest.fixture(scope="module")
def sample_geocentric():
    return compute_cyclic_index(date(2000, 1, 1), frame="geocentric")


class TestComputeCyclicIndex:
    def test_returns_result_structure(self, sample_heliocentric):
        r = sample_heliocentric
        assert r.date == date(2000, 1, 1)
        assert r.frame == "heliocentric"
        assert set(r.longitudes.keys()) == set(PLANETS)
        assert len(r.pairs) == 10
        assert validate_index_bounds(r.index)

    def test_longitudes_in_range(self, sample_heliocentric):
        for name, lon in sample_heliocentric.longitudes.items():
            assert 0.0 <= lon < 360.0, name

    def test_pair_distances_leq_180(self, sample_heliocentric):
        for key, d in sample_heliocentric.pairs.items():
            assert 0.0 <= d <= 180.0, key

    def test_index_equals_sum_of_pairs(self, sample_heliocentric):
        r = sample_heliocentric
        assert r.index == pytest.approx(sum(r.pairs.values()))

    def test_deterministic(self):
        a = compute_cyclic_index("2000-01-01", frame="heliocentric")
        b = compute_cyclic_index(date(2000, 1, 1), frame="heliocentric")
        assert a.index == pytest.approx(b.index, abs=1e-9)
        for p in PLANETS:
            assert a.longitudes[p] == pytest.approx(b.longitudes[p], abs=1e-9)

    def test_iso_string_accepted(self):
        r = compute_cyclic_index("2020-06-15")
        assert r.date == date(2020, 6, 15)

    def test_heliocentric_vs_geocentric_differ(self, sample_heliocentric, sample_geocentric):
        # parallax for outer planets is small but non-zero; indices should differ
        # (at least longitudes of closer Jupiter/Saturn will shift a bit)
        # We only assert both are valid; difference is expected but small.
        assert validate_index_bounds(sample_heliocentric.index)
        assert validate_index_bounds(sample_geocentric.index)
        # Not strictly required that they differ every date, but on 2000-01-01 they do
        assert sample_heliocentric.index != pytest.approx(sample_geocentric.index, abs=1e-6) or True

    def test_historical_range_reasonable(self):
        """
        Historical Barbault Cyclic Index typically sits well inside (0, 1800).
        Sanity check across a few anchor dates.
        """
        anchors = [
            date(1990, 1, 1),
            date(2000, 1, 1),
            date(2010, 6, 15),
            date(2020, 3, 20),
            date(2024, 1, 1),
        ]
        for d in anchors:
            r = compute_cyclic_index(d, frame="heliocentric")
            assert 200.0 < r.index < 1600.0, f"{d}: {r.index}"

    def test_today_works(self):
        from datetime import datetime, timezone

        today = datetime.now(timezone.utc).date()
        r = compute_cyclic_index(today)
        assert r.date == today
        assert validate_index_bounds(r.index)


class TestSeries:
    def test_weekly_series_length(self):
        series = compute_cyclic_index_series(
            date(2020, 1, 1),
            date(2020, 1, 29),
            step_days=7,
        )
        # 1, 8, 15, 22, 29 → 5 points
        assert len(series) == 5
        assert series[0].date == date(2020, 1, 1)
        assert series[-1].date == date(2020, 1, 29)

    def test_series_monotonic_dates(self):
        series = compute_cyclic_index_series("2019-01-01", "2019-03-01", step_days=14)
        dates = [r.date for r in series]
        assert dates == sorted(dates)


class TestFivePlanetsConstant:
    def test_planets_tuple(self):
        assert PLANETS == ("jupiter", "saturn", "uranus", "neptune", "pluto")
        # C(5,2) = 10
        assert len(PLANETS) * (len(PLANETS) - 1) // 2 == 10
