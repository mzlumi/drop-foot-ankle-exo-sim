# Actuator sizing and torque control (Parts C and E)

`python analysis/part_c.py` then `python analysis/part_e.py`. The motor is
the maxon EC 45 flat 411812 ([`actuator/MOTOR.md`](../../actuator/MOTOR.md));
the models are in `dropfoot.actuator` and `dropfoot.sea_control`.

## C1. Torque requirement

The requirement is the tibialis anterior moment that the weak muscle no
longer produces, 1.2 x (healthy minus adapted 25% drop foot), clipped at
zero, each the mean over 3 seeds on a 1% grid of the right stride
(`requirement.csv`, `figures/actuator_requirement.png`). It has two parts:
the eccentric braking of the foot after heel strike (peak **13.6 N m at 8% of
the cycle**) and the swing lift (up to about 7 N m at 69%). The stride of the
adapted gait is 1.355 s. The peak sets the torque limit of the device
(13.61 N m in `actuator_fit.json`).

## C2 and C3. Motor model and the (N, k) sweep

Gear ratio N from 20 to 150 and series stiffness k from 50 N m/rad to rigid,
702 designs (`sweep.csv`, `figures/actuator_sweep.png`,
`figures/actuator_torque_speed.png`). Each design drives the requirement
along a joint trajectory; a design is feasible if the peak motor speed, the
RMS current over a stride (the continuous rating, 3.21 A) and the peak
voltage (24 V, back EMF plus resistive drop) are all within limits. Energy is
the electrical energy per stride without regeneration.

**Which joint trajectory.** The device is there to restore a normal ankle
motion, so the design trajectory is the normative ankle angle (Camargo et al.
2021, 1.2 m/s, mean of 20 subjects) on the model's stride time. On the
adapted model's own ankle trajectory **no design is feasible**
(`sweep_model_trajectory.csv`; the lowest RMS current over all designs is
3.64 A). That trajectory has the foot slap that drop foot causes: a peak
ankle velocity of 15.2 rad/s and acceleration of 2100 rad/s^2, against 4.0
rad/s and 66 rad/s^2 in normative walking. Through a reflected motor inertia
of 0.10 kg m^2 at N = 75 the slap alone would need more than 200 N m. A real
device that follows a slapping foot is not what is being sized; one that
holds the foot to a normal trajectory is.

## C4. Chosen design

Rule (fixed in `part_c.py`): among the feasible designs, the most compliant
one within 2% of the lowest energy, because compliance protects the gearbox
from impacts and makes torque sensing through the spring easier.

| Design | N | k (N m/rad) | Energy/stride (J) | With regeneration (J) | RMS / peak current (A) | Peak speed (rad/s) | Peak voltage (V) |
|---|---|---|---|---|---|---|---|
| Chosen | 75 | 1081 | 6.76 | 6.03 | 1.79 / 6.59 | 301 | 11.3 |
| Rigid, same N | 75 | rigid | 6.79 | 6.04 | 1.79 / 6.17 | 301 | 11.3 |
| Best rigid | 80 | rigid | 6.75 | 5.91 | 1.74 / 5.83 | 322 | 12.1 |

250 of the 702 designs are feasible; the lowest energy is 6.68 J.

**The spring saves almost no energy here (0.4%).** Series elasticity saves
motor work when the spring stores and returns a large share of the joint
work at a frequency near its resonance with the load, as for ankle push-off
in prostheses and plantarflexion exoskeletons (Au and Herr 2008). A
dorsiflexion assist needs small torques at large ankle velocities: the spring
deflection is a fraction of a degree, stores little energy, and the cost is
dominated by copper losses that depend on the torque, not the stiffness. The
spring is kept for torque sensing and impact tolerance (the role it has in
Part E), not for energy.

## E. Torque controller

PID on the spring torque plus feedforward, 1 kHz control with one sample of
computation delay, a 1 kHz current loop and the motor inductance (`control.json`,
`figures/sea_bode.png`, `figures/sea_tracking.png`). The feedforward is the
desired torque plus a model term: the reflected inertia and damping times
the motor acceleration and velocity needed to follow the joint plus the
desired spring deflection, and the derivative gain on the filtered
reference, so that the model term does not fight the derivative of the
feedback at the locked resonance. The model term needs the joint angle and
its derivatives along the stride.
Gains by pole placement for a closed-loop natural frequency f_c, which must
lie above the locked-output resonance (16.4 Hz with N = 75, k = 1081).

| f_c (Hz) | -3 dB bandwidth, static FF (Hz) | Gait tracking RMS error (N m) | Small signal |
|---|---|---|---|
| **20** | **28.8** | **0.21 (1.5% of peak)** | **ok** |
| 25 | 46.8 | 0.19 | ok |
| 30 | 62.7 | 0.17 | ok |
| 35, 40 | 76, 82 | 0.13, 0.10 | more than 6 dB of peaking |
| 45 to 80 | none | 1.9 to 6.1 | unstable |

Rule: the lowest f_c whose small-signal loop is stable with less than 6 dB
peaking, with a bandwidth of at least 10 Hz without the model feedforward,
and gait tracking below 10% of the peak torque. **f_c = 20 Hz** (kp 0.487
A/N m, ki 37.4 A/(N m s), kd 0.0165 A s/N m).

* **Bandwidth.** 28.8 Hz with feedback and static feedforward, 134 Hz with
  the model feedforward. At the full 13.6 N m amplitude the current and
  voltage limits change no gain by more than 1 dB up to 200 Hz, the top of
  the tested range, so the large-signal bandwidth is also 28.8 Hz.
* **Tracking the gait requirement.** RMS error 0.21 N m (1.5%), peak current
  11.4 A (under the 15 A drive limit), peak voltage 11.4 V, no clipping.
  Without the model feedforward the error is 1.87 N m (14%).
* **Reduced model for the simulation.** A first-order lag plus a pure delay
  is fitted to the closed loop. With the model feedforward the fit is a 1 ms
  delay and no lag (0.21 N m RMS), so it would make the simulated device
  ideal. The device in the experiment uses the fit **without** the model
  feedforward, an 8 ms delay and a 3.3 ms time constant (1.16 N m RMS), with
  the 13.61 N m limit (`actuator_fit.json`): the conservative case, which
  does not rely on knowing the ankle trajectory ahead of time.
