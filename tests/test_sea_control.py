import dataclasses

import numpy as np
import pytest

from dropfoot.actuator import load_motor
from dropfoot.sea_control import (
    SEA,
    bandwidth,
    design,
    first_order_delay,
    fit_first_order_delay,
    frequency_response,
    simulate,
)

MOTOR, EXTRA = load_motor()
SEA0 = SEA(MOTOR, ratio=100, stiffness=300.0, eta=EXTRA["gear_efficiency"], inductance=EXTRA["inductance"])


def test_design_places_locked_output_poles():
    ctrl = design(SEA0, bandwidth_hz=15.0, zeta=0.7)
    w = 2 * np.pi * 15.0
    # J_r s^2 + (b_r + Kd k) s + k (1 + Kp) has natural frequency w and damping 0.7
    assert np.sqrt(SEA0.stiffness * (1 + ctrl.kp) / SEA0.j_r) == pytest.approx(w)
    assert (SEA0.b_r + ctrl.kd * SEA0.stiffness) / (2 * SEA0.j_r * w) == pytest.approx(0.7)


def test_constant_torque_is_reached_with_locked_output():
    ctrl = design(SEA0, 15.0)
    t = np.arange(0.0, 0.6, ctrl.period)
    tau_d = np.where(t > 0.05, 5.0, 0.0)
    tr = simulate(SEA0, ctrl, t, tau_d)
    assert tr.tau[-1] == pytest.approx(5.0, abs=0.02)
    # static current: 5 N m / (eta N K_t)
    assert tr.current[-1] == pytest.approx(5.0 / SEA0.torque_per_amp, rel=0.02)


def test_saturation_limits_current_and_voltage():
    ctrl = design(SEA0, 15.0)
    t = np.arange(0.0, 0.3, ctrl.period)
    tau_d = np.where(t > 0.02, 200.0, 0.0)  # far beyond what the drive can give
    tr = simulate(SEA0, ctrl, t, tau_d)
    assert np.max(np.abs(tr.current)) <= MOTOR.peak_current * 1.05
    assert np.max(np.abs(tr.voltage)) <= MOTOR.supply_voltage + 1e-9
    assert tr.current_clipped.any()
    free = simulate(SEA0, ctrl, t, tau_d, saturate=False)
    assert np.max(np.abs(free.current)) > 2 * MOTOR.peak_current


def test_low_frequency_gain_is_one_and_bandwidth_is_found():
    ctrl = design(SEA0, 15.0, model_feedforward=False)
    f = np.array([0.5, 2.0, 5.0, 10.0, 20.0, 40.0, 80.0])
    g, ph = frequency_response(SEA0, ctrl, f)
    assert g[0] == pytest.approx(1.0, abs=0.02)
    assert abs(ph[0]) < 0.05
    bw = bandwidth(f, g)
    assert 5.0 < bw < 80.0


def test_fit_recovers_known_lag():
    dt = 1e-3
    t = np.arange(0.0, 1.0, dt)
    u = np.where((t > 0.1) & (t < 0.5), 4.0, 0.0) + 2.0 * np.sin(2 * np.pi * 3 * t)
    y = first_order_delay(u, dt, time_constant=0.012, delay=0.006)
    tc, delay, rms = fit_first_order_delay(u, y, dt, taus=np.array([0.0, 0.008, 0.012, 0.02]))
    assert (tc, delay) == (0.012, pytest.approx(0.006))
    assert rms < 1e-12


def test_first_order_delay_matches_step_response():
    dt = 1e-3
    u = np.ones(200)
    y = first_order_delay(u, dt, 0.02, 0.005)
    i = np.arange(200)
    # the command arrives after 5 steps and the lag integrates it from the next step on
    np.testing.assert_allclose(y[6:], 1 - np.exp(-(i[6:] - 5) * dt / 0.02), atol=1e-12)
    assert np.all(y[:6] == 0.0)
