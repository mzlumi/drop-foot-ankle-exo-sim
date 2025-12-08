import numpy as np
import pytest
from synthetic import gait_storage

from dropfoot.gait import (
    PERCENT,
    Stride,
    contact_events,
    crossing_time,
    find_strides,
    normalize,
    normalize_strides,
    side_label,
)
from dropfoot.io import Storage


def test_crossing_time_interpolates_between_samples():
    t = np.array([0.0, 0.01, 0.02])
    y = np.array([0.0, 0.02, 0.12])
    assert crossing_time(t, y, 2, 0.05) == pytest.approx(0.013)


def test_strides_match_known_events_to_well_below_one_sample():
    sto, ev = gait_storage(dt=0.005, ramp=0.05)
    strides = find_strides(sto, "r")
    assert len(strides) == len(ev["hs_r"]) - 1
    for s, hs, to, nxt in zip(strides, ev["hs_r"], ev["to_r"], ev["hs_r"][1:]):
        assert s.heel_strike == pytest.approx(hs, abs=1e-6)
        assert s.toe_off == pytest.approx(to, abs=1e-6)
        assert s.next_heel_strike == pytest.approx(nxt, abs=1e-6)
        assert s.stance_fraction == pytest.approx((to - hs) / (nxt - hs), abs=1e-6)
        assert s.length == pytest.approx(1.3, abs=0.01)


def test_both_sides_sorted_and_skip_first():
    sto, ev = gait_storage()
    both = find_strides(sto)
    assert [s.heel_strike for s in both] == sorted(s.heel_strike for s in both)
    assert {s.side for s in both} == {"l", "r"}
    skipped = find_strides(sto, "r", skip_first=2)
    assert skipped[0].heel_strike == pytest.approx(ev["hs_r"][2], abs=1e-6)


def test_short_bump_does_not_start_a_stride():
    sto, ev = gait_storage()
    f = sto["leg1_r.grf_norm_y"].copy()
    mid = 0.5 * (ev["to_r"][1] + ev["hs_r"][2])
    f[(sto.time > mid) & (sto.time < mid + 0.03)] = 0.3  # 30 ms bump in swing
    data = sto.data.copy()
    data[:, sto.index("leg1_r.grf_norm_y")] = f
    strides = find_strides(Storage(sto.labels, sto.time, data), "r")
    assert len(strides) == len(ev["hs_r"]) - 1
    # the bump is merged: the stride still ends at the true next heel strike
    assert strides[1].next_heel_strike == pytest.approx(ev["hs_r"][2], abs=1e-6)


def test_contact_events_returns_all_crossings():
    sto, ev = gait_storage()
    hs, to = contact_events(sto.time, sto["leg1_r.grf_norm_y"])
    np.testing.assert_allclose(hs, ev["hs_r"], atol=1e-6)
    np.testing.assert_allclose(to, ev["to_r"], atol=1e-6)


def test_normalize_maps_heel_strikes_to_0_and_100_percent():
    s = Stride("r", 1.0, 1.6, 2.0, 1.3)
    t = np.linspace(0, 3, 3001)
    out = normalize(t, t, s)
    assert out[0] == pytest.approx(1.0) and out[-1] == pytest.approx(2.0)
    assert out[50] == pytest.approx(1.5)
    assert s.percent(1.6) == pytest.approx(60.0)


def test_normalize_strides_stacks_rows_and_scales():
    t = np.linspace(0, 4, 801)
    sto = Storage(("x",), t, np.sin(2 * np.pi * t)[:, None])
    strides = [Stride("r", 1.0, 1.6, 2.0, 1.0), Stride("r", 2.0, 2.6, 3.0, 1.0)]
    rows = normalize_strides(sto, "x", strides, scale=2.0)
    assert rows.shape == (2, len(PERCENT))
    np.testing.assert_allclose(rows[0], rows[1], atol=1e-3)
    np.testing.assert_allclose(rows[0], 2 * np.sin(2 * np.pi * PERCENT / 100), atol=1e-3)


def test_side_label():
    assert side_label("ankle_angle_{s}", "r") == "ankle_angle_r"
    assert side_label("{leg}.grf_norm_y", "l") == "leg0_l.grf_norm_y"
