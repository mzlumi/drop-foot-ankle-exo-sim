"""Camargo loader on a synthetic trial written in the dataset's own format (MATLAB tables)."""

import numpy as np
import pandas as pd
import pytest

from dropfoot import camargo
from dropfoot.gait import merge_contacts
from synthetic import contact_force

MASS = 70.0
STRIDE, STANCE, FIRST_HS = 1.1, 0.6, 0.3
RAMP = 0.05
GYRO_DELAY = 0.015  # s: IMU stamps are this late


def shank_angle(t):
    """Shank angle (rad) with a once-per-stride pattern."""
    ph = 2 * np.pi * (t - FIRST_HS) / STRIDE
    return 0.4 * np.sin(ph) + 0.1 * np.sin(2 * ph + 0.5)


def write_trial(root, gyro_sign=-1, duration=40.0):
    """One subject folder with conditions, fp, ik, id and imu tables."""
    import matio

    folder = root / "AB99" / "01_01_20" / "treadmill"
    t1 = np.arange(0, duration, 0.001)
    t2 = np.arange(0, duration, 0.005)
    hs = np.arange(FIRST_HS, duration, STRIDE)
    to = hs + STANCE * STRIDE
    f = MASS * camargo.G * contact_force(t1, list(hs), list(to), ramp=RAMP)
    f[(f == 0) & (np.arange(len(t1)) % 37 == 0)] = 0.045 * MASS * camargo.G  # swing spikes
    th = shank_angle(t2)
    ang = np.degrees(th)
    hip, knee = 0.5 * ang + 5.0, 0.5 * ang - 5.0  # pelvis_tilt + hip + knee = shank angle
    w = np.gradient(th, t2)
    gyro = gyro_sign * np.interp(t2 - GYRO_DELAY, t2, w)
    tables = {
        "conditions": {"speed": pd.DataFrame({"Header": t1, "Speed": np.where(t1 < 10, 0.5, 1.2)})},
        "fp": {"data": pd.DataFrame({"Header": t1, "Treadmill_R_vy": f})},
        "ik": {
            "data": pd.DataFrame(
                {"Header": t2, "pelvis_tilt": 0 * t2, "hip_flexion_r": hip, "knee_angle_r": knee, "ankle_angle_r": ang}
            )
        },
        "id": {"data": pd.DataFrame({"Header": t2, "ankle_angle_r_moment": -MASS * np.cos(th)})},
        "imu": {"data": pd.DataFrame({"Header": t2, "shank_Gyro_Y": gyro})},
    }
    for sensor, contents in tables.items():
        (folder / sensor).mkdir(parents=True)
        matio.save_to_mat(str(folder / sensor / "treadmill_01_01.mat"), contents)
    return camargo.TrialFiles("AB99", "treadmill_01_01", folder)


@pytest.fixture(scope="module")
def trial(tmp_path_factory):
    return write_trial(tmp_path_factory.mktemp("camargo"))


def test_speed_windows_drop_settling_time():
    t = np.arange(0, 30, 0.001)
    speed = pd.DataFrame({"Header": t, "Speed": np.select([t < 10, t < 20], [0.5, 1.2], 0.9)})
    (w,) = camargo.speed_windows(speed, 1.2, settle=5.0)
    assert w[0] == pytest.approx(15.0, abs=1e-3)
    assert w[1] == pytest.approx(20.0, abs=1e-2)
    assert camargo.speed_windows(speed, 1.5) == []


def test_merge_contacts_removes_chatter_and_spikes():
    hs = np.array([1.0, 1.598, 1.7, 2.1, 2.105])
    to = np.array([1.595, 1.6, 1.702, 2.102, 2.7])
    a, b = merge_contacts(hs, to, min_gap=0.05, min_stance=0.1)
    # 1.0 to 1.6 is one contact (chatter at toe-off), 1.7 is a spike, 2.1 to 2.7 merges a bounce
    np.testing.assert_allclose(a, [1.0, 2.1])
    np.testing.assert_allclose(b, [1.6, 2.7])


def test_force_events_recover_5pct_crossings_despite_swing_spikes(trial):
    fp = camargo.load_table(trial.path("fp"))
    hs, to = camargo.force_events(fp, MASS)
    true_hs = np.arange(FIRST_HS, 40, STRIDE)[:-1] + 0.05 * RAMP
    assert len(hs) == len(true_hs)
    np.testing.assert_allclose(hs, true_hs, atol=1.5e-3)
    np.testing.assert_allclose(to, true_hs - 0.1 * RAMP + STANCE * STRIDE, atol=1.5e-3)


def test_strides_from_events_rejects_outliers():
    hs = np.array([0.0, 1.0, 2.0, 3.0, 3.5, 4.5, 5.5])
    to = np.array([0.6, 1.6, 2.6, 3.45, 4.1, 5.2, 6.1])
    strides = camargo.strides_from_events(hs, to, [(0.0, 10.0)])
    # 3.0 to 3.5 is too short; 4.5 to 5.5 has 70% stance
    assert [s.heel_strike for s in strides] == [0.0, 1.0, 2.0, 3.5]


def test_align_gyro_recovers_sign_and_delay(trial):
    ik = camargo.load_table(trial.path("ik"))
    imu = camargo.load_table(trial.path("imu"))
    a = camargo.align_gyro(ik, imu)
    assert a.sign == -1 and a.ok
    assert a.lag == pytest.approx(-GYRO_DELAY, abs=1e-3)
    fixed = camargo.aligned_imu(imu, a)
    w = camargo.shank_velocity_ik(ik)
    g = np.interp(ik["Header"], fixed["Header"], fixed["shank_gyro"])
    inner = slice(100, -100)
    assert np.max(np.abs(g[inner] - w[inner])) < 0.03 * np.max(np.abs(w))


def test_align_gyro_rejects_unrelated_signal(trial):
    ik = camargo.load_table(trial.path("ik"))
    rng = np.random.default_rng(0)
    imu = pd.DataFrame({"Header": ik["Header"], "shank_Gyro_Y": rng.normal(size=len(ik))})
    assert not camargo.align_gyro(ik, imu).ok


def test_subject_curves_and_aggregate(trial, tmp_path):
    curves, alignment = camargo.subject_curves(trial, MASS, 1.2)
    n = len(curves["stance_pct"])
    assert 20 <= n <= 27  # 25 s of plateau after settling
    np.testing.assert_allclose(curves["stance_pct"], 100 * STANCE - 100 * 0.1 * RAMP / STRIDE, atol=0.2)
    # the curves are phase-locked to heel strike, so every stride is the same
    ph = 2 * np.pi * (camargo.PERCENT / 100 * STRIDE + 0.05 * RAMP) / STRIDE
    expected = np.degrees(0.4 * np.sin(ph) + 0.1 * np.sin(2 * ph + 0.5))
    np.testing.assert_allclose(curves["ankle_angle"].mean(axis=0), expected, atol=0.2)
    np.testing.assert_allclose(curves["ankle_moment"].mean(axis=0), -np.cos(np.radians(expected)), atol=0.01)
    assert curves["vertical_grf"].max() == pytest.approx(1.0, abs=0.01)
    assert curves["shank_gyro"].shape == (n, 101)

    other = {k: v + 1.0 for k, v in curves.items()}
    df = camargo.aggregate({"A": curves, "B": other})
    np.testing.assert_allclose(df["ankle_angle_sd"], np.sqrt(0.5), rtol=1e-6)
    assert df.attrs["n_subjects"]["shank_gyro"] == 2

    path = tmp_path / "norm.csv"
    camargo.write_normative(df, path, 1.2, ["A", "B"], 2 * n)
    text = path.read_text()
    assert "Camargo" in text and "CC BY 4.0" in text
    back = camargo.read_normative(path)
    np.testing.assert_allclose(back["ankle_angle_mean"], df["ankle_angle_mean"], rtol=1e-4, atol=1e-4)
