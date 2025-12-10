"""The active AFO's phase-based controller: states and torques, and the Lua
device in active mode against the full Python twin (gyroscope, detector,
controller, actuator)."""

import math
import shutil

import numpy as np
import pytest

from dropfoot.detector import Detector, DetectorConfig
from dropfoot.device import ActuatorLag
from dropfoot.fsm import EARLY, OFF, SWING, TRANSPARENT, FSMConfig, PhaseController
from dropfoot.sensor import Gyro, GyroConfig

from test_device import run_device

LUA = shutil.which("lua") is not None


def test_states_and_torques():
    cfg = FSMConfig(brake_nms_per_rad=2.0, kp_nm_per_rad=40.0, kd_nms_per_rad=0.5, target_rad=0.1)
    c = PhaseController(cfg)
    assert c.update(0.0, 0, -1.0, 0.0, -3.0) == 0.0 and c.state == OFF
    # heel strike: brake plantarflexion only
    assert c.update(1.0, 1, 0.02, 0.0, -3.0) == pytest.approx(6.0) and c.state == EARLY
    assert c.update(1.01, 0, 0.03, 0.0, 1.0) == 0.0
    # phase past early_frac: transparent, whatever the motion
    assert c.update(1.2, 0, 0.15, -0.2, -5.0) == 0.0 and c.state == TRANSPARENT
    # toe-off: PD toward the target, never negative
    assert c.update(1.7, 2, 0.6, -0.1, 0.4) == pytest.approx(40.0 * 0.2 - 0.5 * 0.4) and c.state == SWING
    assert c.update(1.8, 0, 0.7, 0.3, 0.0) == 0.0
    # no heel strike within the timeout: back to transparent
    assert c.update(1.7 + cfg.swing_timeout_s + 0.01, 0, 1.0, -0.2, 0.0) == 0.0 and c.state == TRANSPARENT


def twin(props: dict, n: int = 3000) -> np.ndarray:
    """Python version of tests/lua/device_driver.lua in active mode."""
    gyro = Gyro(GyroConfig())
    det = Detector(DetectorConfig())
    fsm = PhaseController(FSMConfig())
    act = ActuatorLag(props["act_delay_s"], props["act_time_constant_s"], props["limit_nm"])
    rows = []
    for i in range(n):
        t = i * 0.001
        event = 0
        if gyro.update(t, math.degrees(4.0 * math.sin(6.0 * t) + 2.0 * math.sin(12.0 * t + 1.0))):
            event = det.update(t, gyro.output)
        cmd = fsm.update(t, event, det.phase(t), 0.2 * math.sin(5.0 * t), 1.0 * math.cos(5.0 * t))
        rows.append((t, act.update(t, cmd), cmd, fsm.state))
    return np.array(rows)


@pytest.mark.skipif(not LUA, reason="lua interpreter not installed")
def test_lua_active_device_matches_python_twin():
    props = {"act_delay_s": 0.008, "act_time_constant_s": 0.012, "limit_nm": 6.0}
    lua = run_device("active", **props)
    py = twin(props)
    np.testing.assert_allclose(lua[:, 4], py[:, 2], rtol=1e-12, atol=1e-12)  # command
    np.testing.assert_allclose(lua[:, 1], py[:, 1], rtol=1e-12, atol=1e-12)  # applied torque
    np.testing.assert_allclose(lua[:, 2], lua[:, 1], atol=1e-12)  # talus_r gets +tau
    np.testing.assert_allclose(lua[:, 3], -lua[:, 1], atol=1e-12)  # tibia_r gets -tau
    states = set(py[:, 3].astype(int))
    assert {EARLY, TRANSPARENT, SWING} <= states  # the mock shank signal drives a full cycle
    assert py[:, 1].max() == pytest.approx(6.0)  # clipped at the limit
    assert py[:, 1].min() >= 0.0
