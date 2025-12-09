"""Device script: moment bookkeeping, actuator response, and the SCONE pulse test."""

import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from dropfoot import ROOT
from dropfoot.device import ActuatorLag, MomentBook
from dropfoot.io import read_sto

DATA = Path(__file__).parent / "data"
LUA = shutil.which("lua") is not None


def run_device(mode, **props):
    args = ["lua", str(Path(__file__).parent / "lua" / "device_driver.lua"), str(ROOT / "scenarios" / "lua"), mode]
    args += [f"{k}={v}" for k, v in props.items()]
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout.split("\n")
    return np.array([[float(x) for x in line.split()] for line in out if line.strip()])


def test_moment_book_applies_only_changes():
    book = MomentBook()
    taus = [0.0, 2.0, 2.0, -1.5, 0.0, 3.25]
    for tau in taus:
        d_talus, d_tibia = book.apply(tau)
        assert d_talus == -d_tibia
        assert book.talus == pytest.approx(tau) and book.tibia == pytest.approx(-tau)


def test_actuator_step_response():
    act = ActuatorLag(delay_s=0.01, time_constant_s=0.02, limit_nm=8.0)
    t = np.arange(0, 0.2, 0.001)
    out = np.array([act.update(float(ti), 10.0) for ti in t])
    assert np.all(out[t < 0.01 - 1e-9] == 0.0)
    after = t >= 0.01 - 1e-9
    expected = 8.0 * (1 - np.exp(-(t[after] - t[after][0]) / 0.02))
    np.testing.assert_allclose(out[after], expected, atol=1e-9)


@pytest.mark.skipif(not LUA, reason="lua interpreter not installed")
def test_lua_device_bookkeeping_constant_mode():
    rows = run_device("constant", constant_nm=4.5, on_time=0.5, off_time=1.7)
    t, applied, talus, tibia = rows[:, 0], rows[:, 1], rows[:, 2], rows[:, 3]
    expected = np.where((t >= 0.5) & (t < 1.7), 4.5, 0.0)
    np.testing.assert_allclose(applied, expected, atol=1e-12)
    np.testing.assert_allclose(talus, expected, atol=1e-12)
    np.testing.assert_allclose(tibia, -expected, atol=1e-12)


@pytest.mark.skipif(not LUA, reason="lua interpreter not installed")
def test_lua_device_passive_spring_and_pair():
    rows = run_device("passive", k_nm_per_rad=30, theta0_rad=0.05)
    t, applied, talus, tibia = rows[:, 0], rows[:, 1], rows[:, 2], rows[:, 3]
    theta = 0.2 * np.sin(5.0 * t)
    np.testing.assert_allclose(applied, -30 * (theta - 0.05), atol=1e-12)
    np.testing.assert_allclose(talus, applied, atol=1e-9)
    np.testing.assert_allclose(tibia, -applied, atol=1e-9)


@pytest.mark.skipif(not LUA, reason="lua interpreter not installed")
def test_lua_actuator_matches_python_twin():
    rows = run_device("constant", constant_nm=12, on_time=0.3, off_time=0.9, act_delay_s=0.012,
                      act_time_constant_s=0.015, limit_nm=9)
    act = ActuatorLag(0.012, 0.015, 9.0)
    py = [act.update(float(t), 12.0 if 0.3 <= t < 0.9 else 0.0) for t in rows[:, 0]]
    np.testing.assert_allclose(rows[:, 1], py, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(rows[:, 2], py, atol=1e-9)


def test_scone_pulse_response_is_mirrored_and_decays():
    """2 N m pulses (+ and -) for 50 ms in mid swing (scenarios/generated/test_pulse_*.scone,
    analysis/device_check.py): the ankle first moves by equal and opposite amounts,
    dorsiflexion for + (the sign convention), with an initial acceleration of the
    order of tau over the foot's inertia about the ankle."""
    s = read_sto(DATA / "device_pulse.sto")
    col = lambda n: s.data[:, s.labels.index(n)]
    t = s.time
    dp = col("ankle_plus") - col("ankle_none")
    dm = col("ankle_minus") - col("ankle_none")
    early = (t > 2.25) & (t <= 2.27 + 1e-9)
    assert np.all(dp[early] > 0) and np.all(dm[early] < 0)
    np.testing.assert_allclose(dp[early], -dm[early], rtol=0.06)
    i = np.searchsorted(t, 2.26 - 1e-9)
    alpha = 2 * dp[i] / 0.01**2
    assert 40 < alpha < 200  # rad/s^2; 2 N m / 0.016 kg m^2 = 125 for a free foot
    # the + pulse is applied only during 2.25 to 2.30 s and the deviation fades afterwards
    torque = col("torque_plus")
    assert np.all(torque[(t > 2.251) & (t < 2.299)] == 2.0) and np.all(torque[(t < 2.249) | (t > 2.301)] == 0.0)
    assert abs(dp[np.searchsorted(t, 2.5)]) < 0.1 * np.max(np.abs(dp))
