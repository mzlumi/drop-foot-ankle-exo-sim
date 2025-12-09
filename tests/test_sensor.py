"""The simulated gyroscope: Python twin against its definition, against the
Lua module run directly, and against a SCONE run (tests/data/imu_tutorial_0-3s.sto)."""

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from dropfoot import ROOT
from dropfoot.io import read_sto
from dropfoot.sensor import Gyro, GyroConfig, ParkMiller, noise_sequence, simulate

DATA = Path(__file__).parent / "data"
CONTROL_STEP = 0.001


def signal(t):
    return 300.0 * np.sin(2 * np.pi * t) + 40.0 * np.cos(7.0 * t)


def test_park_miller_known_values():
    # x1 = 16807 for seed 1, and the classic check value x_10000 = 1043618065
    rng = ParkMiller(1)
    rng.uniform()
    assert rng.state == 16807
    for _ in range(9999):
        rng.uniform()
    assert rng.state == 1043618065


def test_noise_is_standard_normal():
    n = noise_sequence(7, 20000)
    assert abs(n.mean()) < 0.03
    assert n.std() == pytest.approx(1.0, abs=0.02)


def test_sampling_hold_and_delay():
    cfg = GyroConfig(rate_hz=100, noise_dps=0.0, bias_dps=2.0, delay_s=0.015)
    t = np.arange(2000) * CONTROL_STEP
    tr = simulate(t, signal(t), cfg)
    expected_k = np.floor((t - cfg.delay_s) / 0.01 + 1e-6).astype(int)
    expected_k[t < cfg.delay_s - 1e-9] = -1
    np.testing.assert_array_equal(tr.output_k, expected_k)
    np.testing.assert_allclose(tr.sample_value, signal(tr.sample_t) + 2.0, atol=1e-9)
    # held between samples
    k = tr.output_k >= 0
    np.testing.assert_allclose(tr.measured[k], tr.sample_value[tr.output_k[k]], atol=0)


def test_gyro_noise_matches_sequence():
    cfg = GyroConfig(noise_dps=0.5, bias_dps=0.0, delay_s=0.0, seed=3)
    t = np.arange(1000) * CONTROL_STEP
    tr = simulate(t, np.zeros_like(t), cfg)
    np.testing.assert_allclose(tr.sample_value, 0.5 * noise_sequence(3, len(tr.sample_value)), atol=1e-12)


@pytest.mark.skipif(shutil.which("lua") is None, reason="lua interpreter not installed")
def test_lua_module_matches_python_twin():
    cfg = GyroConfig(rate_hz=100, noise_dps=0.5, bias_dps=2.0, delay_s=0.012, seed=11)
    out = subprocess.run(
        ["lua", str(Path(__file__).parent / "lua" / "gyro_driver.lua"), str(ROOT / "scenarios" / "lua"),
         "100", "0.5", "2.0", "0.012", "11"],
        capture_output=True, text=True, check=True,
    ).stdout.split("\n")
    rows = np.array([[float(x) for x in line.split()] for line in out if line.strip()])
    t = np.arange(2000) * CONTROL_STEP
    g = Gyro(cfg)
    py = []
    for ti in t:
        ti = float(ti)
        g.update(ti, 300.0 * np.sin(2 * np.pi * ti) + 40.0 * np.cos(7.0 * ti))
        py.append((g.output, g.output_k))
    py = np.array(py)
    np.testing.assert_array_equal(rows[:, 2], py[:, 1])
    np.testing.assert_allclose(rows[:, 1], py[:, 0], rtol=1e-13, atol=1e-12)


def test_scone_run_matches_python_twin():
    """In SCONE the frame at time t > 0 is written before the controller
    update at t, so logged controller state is one control step old (the
    first frame comes after the initial update at t = 0)."""
    s = read_sto(DATA / "imu_tutorial_0-3s.sto")
    col = lambda n: s.data[:, s.labels.index(n)]
    cfg = GyroConfig()  # the values in scenarios/healthy_imu.scone
    t = s.time
    sample_k = col("imu.sample_k").astype(int)
    output_k = col("imu.output_k").astype(int)
    lag = np.maximum(t - CONTROL_STEP, 0.0)
    np.testing.assert_array_equal(sample_k, np.floor(lag / 0.01 + 1e-6).astype(int))
    expected = np.floor((lag - cfg.delay_s) / 0.01 + 1e-6).astype(int)
    expected[lag < cfg.delay_s - 1e-9] = -1
    np.testing.assert_array_equal(output_k, expected)

    true_k = {}
    for k, v in zip(sample_k, col("imu.sample_true")):
        true_k.setdefault(k, v)
    noise = noise_sequence(cfg.seed, max(true_k) + 1)
    have = output_k >= 0
    twin = np.array([true_k[k] + cfg.bias_dps + cfg.noise_dps * noise[k] for k in output_k[have]])
    # the .sto keeps 6 significant digits
    np.testing.assert_allclose(col("imu.measured")[have], twin, rtol=2e-6, atol=2e-3)
