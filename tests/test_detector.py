"""The gait-event detector: known events on a synthetic shank signal, causality,
identical events in Lua and Python, and agreement with a SCONE run."""

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from dropfoot import ROOT
from dropfoot.detector import Detector, DetectorConfig, detect, match_events
from dropfoot.io import read_sto

DATA = Path(__file__).parent / "data"
PERIOD = 0.01
STRIDE = 1.1


def bump(ph, centre, width, height):
    d = (ph - centre + 0.5) % 1.0 - 0.5  # periodic distance
    return height * np.exp(-0.5 * (d / width) ** 2)


def shank_signal(t, stride=STRIDE, hs0=0.2):
    """Shank-like pattern: HS at phase 0, a minimum just after it, a pre-swing
    minimum at 58%, a swing peak at 85% and a zero crossing near 95%."""
    ph = ((t - hs0) / stride) % 1.0
    return (
        -60.0
        + bump(ph, 0.04, 0.02, -200.0)
        + bump(ph, 0.58, 0.03, -190.0)
        + bump(ph, 0.85, 0.06, 470.0)
        + bump(ph, 0.30, 0.10, 40.0)
    )


def samples(duration=12.0, noise=0.0, seed=0):
    t = np.arange(0.0, duration, PERIOD)
    y = shank_signal(t)
    if noise:
        y = y + np.random.default_rng(seed).normal(0, noise, len(t))
    return t, y


def sample_minima(t, y, lo, hi, hs0=0.2):
    """Sample time of the minimum in each stride's phase window [lo, hi)."""
    out = []
    for k in range(int((t[-1] - hs0) / STRIDE) + 1):
        a, b = hs0 + (k + lo) * STRIDE, hs0 + (k + hi) * STRIDE
        i = (t >= a) & (t < b)
        if i.any() and b < t[-1]:
            out.append(t[i][np.argmin(y[i])])
    return np.array(out)


def test_events_on_synthetic_signal():
    t, y = samples()
    ev = detect(t, y).as_arrays()
    # the signal starts in a swing peak, so every heel strike is found
    true_hs_min = sample_minima(t, y, -0.05, 0.2)
    np.testing.assert_allclose(ev["hs_time"], true_hs_min, atol=1e-12)
    true_to = sample_minima(t, y, 0.45, 0.7)
    to = ev["to_time"]
    np.testing.assert_allclose(to, true_to[-len(to):], atol=1e-12)
    assert np.all(ev["hs_detect"] >= ev["hs_time"]) and np.all(ev["to_detect"] > ev["to_time"])


def test_zero_crossing_feature_is_interpolated():
    t, y = samples()
    ev = detect(t, y, DetectorConfig(hs_feature="zero")).as_arrays()
    fine = np.arange(0.0, 12.0, 1e-5)
    yf = shank_signal(fine)
    down = np.flatnonzero((yf[:-1] >= 0) & (yf[1:] < 0))
    zc = fine[down]
    for h in ev["hs_time"]:
        assert np.min(np.abs(zc - h)) < 2e-4  # linear interpolation over 10 ms


def test_phase_estimate():
    t, y = samples(duration=20.0)
    d = Detector()
    phases = []
    for ti, yi in zip(t, y):
        d.update(float(ti), float(yi))
        phases.append(d.phase(float(ti)))
    assert d.mean_stride() == pytest.approx(STRIDE, abs=0.011)
    assert max(phases) <= 1.0 and min(phases) == -1.0
    # half a stride after a late heel strike, the phase is about 0.5
    i = np.searchsorted(t, d.hs_time + 0.5 * STRIDE)
    assert -1 < phases[i] < 1


def test_detector_is_causal():
    """Events confirmed before time tc do not change when every later sample changes."""
    t, y = samples(noise=1.0)
    full = detect(t, y).as_arrays()
    tc = 7.3
    y2 = y.copy()
    y2[t > tc] = np.random.default_rng(1).normal(0, 300, (t > tc).sum())
    cut = detect(t, y2).as_arrays()
    for key in ("hs", "to"):
        a = full[f"{key}_detect"] <= tc
        b = cut[f"{key}_detect"] <= tc
        np.testing.assert_array_equal(full[f"{key}_time"][a], cut[f"{key}_time"][b])
        np.testing.assert_array_equal(full[f"{key}_detect"][a], cut[f"{key}_detect"][b])


def test_match_events_counts_missed_and_false():
    m = match_events([1.0, 2.0, 3.0], [1.02, 2.5, 3.01, 3.05], [1.05, 2.55, 3.04, 3.08])
    assert m.missed == 1 and m.false == 2 and m.n_true == 3
    np.testing.assert_allclose(m.errors, [0.02, 0.01])
    np.testing.assert_allclose(m.latency, [0.05, 0.04])


@pytest.mark.skipif(shutil.which("lua") is None, reason="lua interpreter not installed")
@pytest.mark.parametrize("feature", ["min", "zero"])
def test_lua_detector_gives_identical_events(feature):
    t, y = samples(duration=15.0, noise=2.0, seed=4)
    text = "\n".join(f"{a:.17g} {b:.17g}" for a, b in zip(t, y)) + "\n"
    out = subprocess.run(
        ["lua", str(Path(__file__).parent / "lua" / "detector_driver.lua"), str(ROOT / "scenarios" / "lua"), feature],
        input=text, capture_output=True, text=True, check=True,
    ).stdout.split("\n")
    rows = np.array([[float(x) for x in line.split()] for line in out if line.strip()])
    d = Detector(DetectorConfig(hs_feature=feature))
    py = []
    for ti, yi in zip(t, y):
        e = d.update(float(ti), float(yi))
        if e == 1:
            py.append((1, ti, d.hs_time, d.hs_detect, d.phase(float(ti))))
        elif e == 2:
            py.append((2, ti, d.to_time, d.to_detect, d.phase(float(ti))))
    py = np.array(py)
    assert rows.shape == py.shape and len(py) > 15
    np.testing.assert_array_equal(rows[:, 0], py[:, 0])
    np.testing.assert_allclose(rows[:, 1:], py[:, 1:], rtol=0, atol=1e-12)


def test_scone_run_gives_the_python_events():
    """The detector inside SCONE (scenarios/healthy_imu.scone) and the twin
    on the logged samples find the same events."""
    s = read_sto(DATA / "imu_tutorial_0-6s.sto")
    col = lambda n: s.data[:, s.labels.index(n)]
    k = col("imu.output_k").astype(int)
    first = np.flatnonzero(np.r_[True, np.diff(k) != 0] & (k >= 0))
    delay = 0.015
    t_avail = k[first] * PERIOD + delay
    ev = detect(t_avail, col("imu.measured")[first]).as_arrays()
    for key in ("hs", "to"):
        logged = np.unique(col(f"det.{key}_time"))
        logged = logged[logged >= 0]
        np.testing.assert_allclose(ev[f"{key}_time"], logged, atol=1e-5)
        assert len(logged) >= 3
