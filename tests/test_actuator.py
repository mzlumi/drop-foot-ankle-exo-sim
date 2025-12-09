"""Energy balance and limiting cases of the SEA model."""

import dataclasses

import numpy as np
import pytest

from dropfoot.actuator import Motor, check_limits, operate, periodic_derivative, torque_requirement

MOTOR = Motor("test", kt=0.05, resistance=0.5, inertia=1e-5, rated_current=5.0, max_speed=1000.0, supply_voltage=48.0)
T = 1.1
N_SAMPLES = 2200


def stride():
    t = np.arange(N_SAMPLES) * T / N_SAMPLES
    ph = 2 * np.pi * t / T
    tau = 8 + 6 * np.sin(ph) + 3 * np.cos(2 * ph + 0.3)
    theta = 0.25 * np.sin(ph + 1.0) + 0.05 * np.sin(3 * ph)
    return t, tau, theta


def test_periodic_derivative_of_sine():
    t = np.arange(1000) / 1000
    d = periodic_derivative(np.sin(2 * np.pi * t), t[1])
    np.testing.assert_allclose(d, 2 * np.pi * np.cos(2 * np.pi * t), atol=1e-3)


@pytest.mark.parametrize("k", [100.0, 500.0, np.inf])
def test_energy_balance_over_a_stride(k):
    """Electrical energy in = copper loss + joint work, because rotor kinetic
    energy and spring energy return to their start values over a period."""
    t, tau, theta = stride()
    op = operate(MOTOR, 60.0, k, t, tau, theta)
    dt = t[1] - t[0]
    copper = np.sum(MOTOR.resistance * op.current**2) * dt
    joint_work = np.sum(tau * periodic_derivative(theta, dt)) * dt
    assert op.energy_regen == pytest.approx(copper + joint_work, rel=1e-3, abs=1e-4)
    assert op.energy_no_regen >= op.energy_regen


def test_spring_work_cancels_over_a_stride():
    t, tau, theta = stride()
    dt = t[1] - t[0]
    k = 300.0
    op = operate(MOTOR, 40.0, k, t, tau, theta)
    out_work = np.sum(tau * periodic_derivative(op.theta_out, dt)) * dt
    joint_work = np.sum(tau * periodic_derivative(theta, dt)) * dt
    assert out_work == pytest.approx(joint_work, abs=1e-6)


def test_stiff_spring_converges_to_rigid():
    t, tau, theta = stride()
    rigid = operate(MOTOR, 60.0, np.inf, t, tau, theta)
    stiff = operate(MOTOR, 60.0, 1e7, t, tau, theta)
    assert stiff.energy_no_regen == pytest.approx(rigid.energy_no_regen, rel=1e-4)
    assert stiff.peak_speed == pytest.approx(rigid.peak_speed, rel=1e-4)


def test_static_torque_needs_only_copper_power():
    t = np.arange(1000) * 1e-3
    tau = np.full_like(t, 10.0)
    op = operate(MOTOR, 50.0, 200.0, t, tau, np.zeros_like(t))
    i = 10.0 / 50.0 / MOTOR.kt
    np.testing.assert_allclose(op.current, i)
    np.testing.assert_allclose(op.voltage, MOTOR.resistance * i)
    np.testing.assert_allclose(op.omega_m, 0.0, atol=1e-12)


def test_gear_efficiency_increases_energy():
    t, tau, theta = stride()
    ideal = operate(MOTOR, 60.0, 400.0, t, tau, theta)
    lossy = operate(MOTOR, 60.0, 400.0, t, tau, theta, eta=0.8)
    assert lossy.energy_no_regen > ideal.energy_no_regen


def test_limits_flag_speed():
    t, tau, theta = stride()
    slow = dataclasses.replace(MOTOR, max_speed=200.0)
    lim = check_limits(operate(slow, 150.0, np.inf, t, tau, theta), slow)
    assert not lim.speed and not lim.ok
    assert check_limits(operate(slow, 20.0, np.inf, t, tau, theta), slow).speed


def test_chosen_motor_file_is_consistent():
    from dropfoot.actuator import load_motor

    motor, extra = load_motor()
    assert motor.kt == pytest.approx(60 / (2 * np.pi * 259), rel=0.01)  # speed constant 259 rpm/V
    no_load = (motor.supply_voltage - motor.resistance * 0.234) / motor.ke
    assert no_load == pytest.approx(6110 * 2 * np.pi / 60, rel=0.015)
    assert 0 < extra["gear_efficiency"] <= 1


def test_torque_requirement_keeps_dorsiflexing_deficit():
    healthy = np.array([0.0, 5.0, 10.0, 2.0])
    weak = np.array([0.0, 1.25, 2.5, 3.0])
    np.testing.assert_allclose(torque_requirement(healthy, weak), [0.0, 4.5, 9.0, 0.0])
