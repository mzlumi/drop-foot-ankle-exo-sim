# Motor for the ankle exoskeleton actuator

**Motor:** maxon EC 45 flat, Ø45 mm, brushless, 70 W, 24 V, with Hall sensors, with cable, part number **411812**.

- Datasheet page: <https://www.maxongroup.com/maxon/view/product/motor/ecmotor/ecflat/ecflat45/411812> (opened 2025-12-09). The numbers below are copied from it into [`motor_ec45flat_411812.toml`](motor_ec45flat_411812.toml).
- The same winding is sold as part 397172 (Ø42.8 mm housing) with the same electrical data.
- maxon lists the part as NRND (not recommended for new designs, still available). That does not matter for a design study, but a build would use its successor in the same series.

Why this motor: flat outrunner motors of this class are common in wearable ankle devices because they give high torque per mass (141 g) and fit beside the shank. Its 128 mN m continuous torque times a reduction of about 100 covers the dorsiflexion assistance torque this project needs (about 10 N m, see `results/actuator/`) and its 10000 rpm limit leaves room for the reduction.

| Datasheet value | Number | Used as |
|---|---|---|
| Nominal voltage | 24 V | supply voltage limit |
| Torque constant | 36.9 mN m/A | K_t (and K_e = 0.0369 V s/rad) |
| Terminal resistance, phase to phase | 0.608 Ω | R |
| Rotor inertia | 181 g cm² | J_m = 1.81e-5 kg m² |
| Nominal current (max. continuous) | 3.21 A | limit on the RMS current over a stride |
| Max. speed | 10000 rpm | limit on the peak motor speed (1047 rad/s) |
| No load speed / no load current | 6110 rpm / 234 mA | check of K_e and of the friction, see below |
| Stall torque / stall current | 1460 mN m / 39.5 A | not a usable limit (thermal) |
| Thermal time constant of the winding | 29.6 s | justifies the RMS current limit: a 1.1 s stride is much shorter |
| Terminal inductance | 0.463 mH | electrical time constant L/R = 0.76 ms, neglected in Part C, kept in Part E |
| Weight | 141 g | |

**Assumptions that are not on the datasheet.**

- **Peak current: 15 A**, the peak output of a maxon ESCON 50/5 servo controller (5 A continuous), which is a typical drive for this motor. The motor datasheet gives no short-term current limit.
- **Viscous friction at the rotor** from the no-load current: b_m = K_t · I_0 / ω_0 = 0.0369 · 0.234 / 640 rad/s = 1.35e-5 N m s/rad. The no-load current is mostly Coulomb friction, so this is a rough lumped number; it is small next to the load torque.
- **Gear efficiency: 0.85** for the reduction stage (a two-stage planetary or a belt plus ball screw would be similar), applied as described in `src/dropfoot/actuator.py`.
- **No regeneration** for the energy per stride (the design number); the ideal regeneration case is reported as a lower bound.

Check of the datasheet constants: the speed constant 259 rpm/V gives K_e = 60 / (2π · 259) = 0.0369 V s/rad, equal to K_t, as it should be in SI units. The no-load speed at 24 V is 6110 rpm = 640 rad/s, and (24 V − 0.608 Ω · 0.234 A) / 0.0369 = 646 rad/s, consistent within 1%.
