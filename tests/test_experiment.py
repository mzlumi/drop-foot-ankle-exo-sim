import numpy as np
import pytest

from dropfoot.experiment import ActuatorFit, active_props, device_stride_metrics, passive_props
from dropfoot.fsm import FSMConfig
from dropfoot.gait import Stride
from dropfoot.io import Storage
from dropfoot.scenarios import device_scenario


def _sto(with_device: bool) -> Storage:
    t = np.arange(0.0, 1.2001, 0.005)
    ankle_power = 100.0 * np.exp(-(((t - 0.6) / 0.05) ** 2))  # push-off burst at 0.6 s
    labels = ["ankle_angle_r.power"]
    cols = [ankle_power]
    if with_device:
        # +2 W for 0.3 s, then -1 W, and it absorbs 30% of the push-off burst
        dev_power = np.where(t < 0.3, 2.0, -1.0) - 0.3 * ankle_power
        labels += ["dev.power", "dev.torque"]
        cols += [dev_power, np.where(t < 0.3, 4.0, 1.0)]
    return Storage(labels=tuple(labels), time=t, data=np.column_stack(cols), name="x")


def test_device_work_and_pushoff_power():
    st = Stride("r", 0.0, 0.7, 1.2, 1.0)
    m = device_stride_metrics(_sto(True), st)
    assert m["device_positive_work_j"] == pytest.approx(0.6, abs=0.02)
    # -1 W for 0.9 s and 30% of the burst's 100 * 0.05 * sqrt(pi) J
    assert m["device_negative_work_j"] == pytest.approx(-0.9 - 0.3 * 5 * np.sqrt(np.pi), abs=0.01)
    assert m["device_peak_power_w"] == pytest.approx(2.0, abs=1e-6)
    assert m["device_peak_torque_nm"] == 4.0
    assert m["peak_pushoff_power_w"] == pytest.approx(0.7 * 100.0 - 1.0, abs=0.01)
    plain = device_stride_metrics(_sto(False), st)
    assert plain["peak_pushoff_power_w"] == pytest.approx(100.0)
    assert plain["device_positive_work_j"] == 0.0


def test_device_scenarios_carry_the_properties():
    text = device_scenario("t", "x", passive_props(40.0), factor=0.25)
    assert "mode = passive" in text and "k_nm_per_rad = 40.0" in text
    assert "tib_ant_r { max_isometric_force.factor = 0.25 }" in text
    assert "ControllerGH2010asym.scone" in text
    text = device_scenario("t", "x", active_props(FSMConfig(), ActuatorFit(0.01, 0.02, 11.0)), factor=0.25)
    for key in ("mode = active", "act_delay_s = 0.01", "limit_nm = 11.0", "kp_nm_per_rad = 30.0", "imu_delay_s = 0.015"):
        assert key in text
