"""Metrics on synthetic trajectories with known answers.

The synthetic gait has a right stride of T = 1.1 s with right heel strikes at
0.3 + 1.1 k s and toe-off at 60% of the stride (gait_storage defaults).
"""

import numpy as np
import pytest
from synthetic import gait_storage

from dropfoot.metrics import (
    asymmetry,
    change_from,
    cost_of_transport,
    gait_summary,
    stride_table,
    symmetry_index,
)

T, HS0, STANCE = 1.1, 0.3, 0.6
A_ANKLE = np.radians(10.0)
W = 2 * np.pi / T


def phase(t):
    """Fraction of the right gait cycle, 0 at the (raw) right heel strike."""
    return ((t - HS0) / T) % 1.0


def planted(t, hs, stance, positions):
    """Foot x: fixed during stance, linear between footholds during swing."""
    knots_t, knots_x = [], []
    for h, x in zip(hs, positions):
        knots_t += [h, h + stance]
        knots_x += [x, x]
    return np.interp(t, knots_t, knots_x)


def build():
    sto0, _ = gait_storage()
    t = sto0.time
    u = phase(t)
    swing = u >= STANCE
    v = (u - STANCE) / (1 - STANCE)  # 0..1 through swing
    ks = np.arange(-1, 8)
    extra = {
        # 20 mm in stance, a half-sine bump of 30 mm in swing
        "toes_r.pos_y": 0.02 + np.where(swing, 0.03 * np.sin(np.pi * v), 0.0),
        "ankle_angle_r": A_ANKLE * np.cos(W * (t - HS0)),
        "ankle_angle_r_u": -A_ANKLE * W * np.sin(W * (t - HS0)),
        "hip_flexion_r": np.radians(30.0) * np.cos(2 * np.pi * (u - 0.85)),
        "knee_angle_r": -np.radians(60.0) * np.where(swing, np.sin(np.pi * v), 0.0),
        "ankle_angle_r.power": np.where(~swing, 200.0 * np.sin(np.pi * u / STANCE), -50.0),
        "calcn_r.pos_x": planted(t, HS0 + T * ks, STANCE * T, 1.3 * ks + 0.7),
        "calcn_l.pos_x": planted(t, HS0 + T / 2 + T * ks, STANCE * T, 1.3 * ks + 1.3),
        "pelvis_tx": 1.3 / T * t,
    }
    sto, events = gait_storage(extra=extra)
    return sto, events


def test_per_stride_metrics_have_known_values():
    sto, _ = build()
    table = stride_table(sto, "r", skip_first=1)
    assert len(table) >= 3
    # mid-swing window is 25-75% of swing: the bump is lowest at its edges
    expected_mtc = 1000 * (0.02 + 0.03 * np.sin(np.pi * 0.25))
    np.testing.assert_allclose(table["min_toe_clearance_mm"], expected_mtc, atol=0.3)
    # events sit 2.5 ms after the raw heel strike (5% of a 50 ms ramp)
    expected_ic = np.degrees(A_ANKLE * np.cos(W * 0.0025))
    np.testing.assert_allclose(table["ankle_at_ic_deg"], expected_ic, atol=0.01)
    # cos peaks at the next heel strike, the end of swing
    np.testing.assert_allclose(table["peak_swing_df_deg"], 10.0, atol=0.01)
    # -d(ankle)/dt = A w sin(w t); largest at 15% of the cycle in the window
    expected_slap = np.degrees(A_ANKLE * W * np.sin(2 * np.pi * (0.15 + 0.0025 / T)))
    np.testing.assert_allclose(table["foot_slap_index_dps"], expected_slap, rtol=2e-3)
    np.testing.assert_allclose(table["peak_hip_flexion_swing_deg"], 30.0, atol=0.01)
    np.testing.assert_allclose(table["peak_knee_flexion_swing_deg"], 60.0, atol=0.05)
    np.testing.assert_allclose(table["peak_ankle_power_w"], 200.0, atol=0.1)
    np.testing.assert_allclose(table["stride_time_s"], T, atol=1e-6)
    np.testing.assert_allclose(table["stance_pct"], 100 * (STANCE * T - 0.005) / T, atol=1e-3)


def test_asymmetry_from_known_step_lengths():
    sto, _ = build()
    a = asymmetry(sto, skip_first=1)
    assert a["step_length_r_m"] == pytest.approx(0.7, abs=1e-6)
    assert a["step_length_l_m"] == pytest.approx(0.6, abs=1e-6)
    assert a["step_length_si_pct"] == pytest.approx(100 * 0.1 / 0.65, abs=1e-4)
    assert a["stance_time_si_pct"] == pytest.approx(0.0, abs=1e-6)


def test_symmetry_index_sign_and_zero():
    assert symmetry_index(1.0, 1.0) == 0.0
    assert symmetry_index(1.1, 0.9) == pytest.approx(20.0)
    assert symmetry_index(0.9, 1.1) == pytest.approx(-20.0)


REPORT = """\
06:38:59 result                    = 0.548434
06:38:59   Gait                    = 0 <- 100 * (0 > 0.05)
06:38:59     step_velocity         = 1.13105
06:38:59   Effort                  = 0.548434 <- 0.1 * 5.48434
06:38:59     effort                = 4653.6
06:38:59     distance              = 11.2889
"""


def test_cost_of_transport_reads_unweighted_effort():
    assert cost_of_transport(REPORT) == pytest.approx(5.48434)


def test_gait_summary_means_sd_and_trial_values():
    sto, _ = build()
    summary = gait_summary(sto, REPORT, skip_first=1)
    d = summary.as_dict()
    assert d["n_strides"] == summary.n_strides >= 3
    assert d["peak_hip_flexion_swing_deg"] == pytest.approx(30.0, abs=0.01)
    assert d["peak_hip_flexion_swing_deg_sd"] == pytest.approx(0.0, abs=0.01)
    assert d["speed_mps"] == pytest.approx(1.3 / T, rel=1e-6)
    assert d["cost_of_transport"] == pytest.approx(5.48434)


def test_change_from_reference():
    out = change_from({"a": 3.0, "b": 1.0}, {"a": 1.0, "b": 1.5}, ["a", "b"])
    assert out == {"delta_a": 2.0, "delta_b": -0.5}
