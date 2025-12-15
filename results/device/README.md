# Device experiment (Part F)

Right tibialis anterior at 25% strength. The hypothesis, the primary metric,
the decision rule and the tuning rule are in the top-level README and were
committed before any of this was run (the completion of the tuning rule
too). Commands, in order:

```
python analysis/part_f.py frozen      # tuning on the frozen controllers
python analysis/part_f.py soft        # how soft a spring the frozen controllers tolerate
python analysis/part_f.py reopt       # prints the 9 re-optimizations (run on the studio)
python analysis/curate_runs.py none_ta25 --dest results/device/none_ta25   # and the two devices
python analysis/part_f.py compare     # table, figure, verdict
```

## Verdict: the hypothesis is rejected

From `verdict.md`, on the means over the three re-optimized seeds:

| Part | Threshold | Value | Seed SD | Result |
|---|---|---|---|---|
| 1. Active AFO toe clearance >= healthy - 10 mm | 26.3 mm | 50.8 mm | 6.3 | holds |
| 2. Active AFO push-off power >= 90% of no device | 111.8 W | 132.7 W | 2.1 | holds |
| 3. Passive AFO push-off power < 85% of no device | 105.5 W | 208.9 W | 32.4 | fails |

Part 3 fails by far more than one seed SD, so the hypothesis is rejected.
Part 1 holds as the decision rule defines it (a lower bound). The sentence of
the hypothesis says "within 10 mm of healthy"; read two-sided, part 1 would
miss too (50.8 mm is 14.5 mm above healthy, a miss of 4.5 mm, less than the
seed SD, so inconclusive). The rule was written as a lower bound because the
concern was a toe that drags; that the adapted model lifts its toe higher than
healthy was not expected.

## Tuning on the frozen controllers

With the adapted reflexes frozen, no device setting lets all three seeds
walk (`frozen.csv`): every passive stiffness from 10 to 160 N m/rad walks in
seed 2 only, and no active swing target walks in any seed. The completed rule
chose k = 160 N m/rad (toe clearance closest to healthy among the walking
runs) and a 10 degree swing target (longest mean time before the fall).

These falls are a property of the optimized model. The soft-spring check
(`frozen_soft_springs.csv`) finds that springs of up to 2.5 N m/rad leave
all seeds walking, while 5 N m/rad (under 2 N m at the ankle's range) already
makes two of three fall. The adapted gaits are effort optima tuned to their
own dynamics, with no reserve for any change at the ankle; people adapt
within a few steps, and the re-optimized condition is the model's version
of that.

## Re-optimized with the device

150 generations from the adapted controller of the same seed, for no device
as well (the control for the extra generations). All nine runs walk.
Convergence: no device converged in all seeds, the active AFO in seeds 1
and 2 (seed 3: 2.5% over the last 40 generations), the passive AFO in seed 3
(seed 1 found walking only at generation 134; seed 2: 1.3%). The comparison
uses the committed equal budget; the unconverged runs are continued
separately as a sensitivity check.

| Metric | Healthy | No device | Passive AFO k160 | Active AFO 10 deg |
|---|---|---|---|---|
| Cost | 0.546 | 0.594 +/- 0.018 | 0.637 +/- 0.083 | 0.563 +/- 0.010 |
| Min toe clearance (mm) | 36.3 +/- 0.3 | 50.8 +/- 12.0 | 50.8 +/- 5.9 | 50.8 +/- 6.3 |
| Push-off power, muscles + device (W) | 126 +/- 1 | 124 +/- 6 | 209 +/- 32 | 133 +/- 2 |
| Push-off power, muscles (W) | 126 +/- 1 | 124 +/- 6 | 113 +/- 9 | 133 +/- 2 |
| Ankle at initial contact (deg) | 0.4 | -7.3 +/- 3.5 | -0.6 +/- 0.6 | +3.7 +/- 0.2 |
| Foot slap index (deg/s) | 782 | 884 +/- 68 | 452 +/- 28 | 833 +/- 57 |
| Peak swing hip flexion (deg) | 46.3 | 56.6 +/- 2.3 | 53.4 +/- 5.4 | 50.0 +/- 2.3 |
| Peak swing knee flexion (deg) | 75.7 | 78.5 +/- 1.7 | 80.0 +/- 2.7 | 75.3 +/- 4.7 |
| Cost of transport, muscles (J/(kg m)) | 5.46 | 5.94 +/- 0.18 | 6.00 +/- 0.51 | 5.63 +/- 0.10 |
| Device work per stride, + / - (J) | | | 12.3 / -12.4 | 3.8 / -4.2 |
| Device peak torque (N m), peak power (W) | | | 38.6, 336 | 13.5, 100 |

The three toe clearance means agree to 0.01 mm by coincidence; the per-seed
values differ (43 to 64 mm, `comparison.csv`). Full table with the frozen
conditions in `comparison.md`, curves in `figures/device_comparison.png`.

**No device.** 150 more generations change little: costs fall from 0.627 to
0.594, toe clearance stays high (50.8 mm, 43 to 64 by seed) and the steppage
stays.

**Passive AFO (160 N m/rad, neutral 0).** It does what a stiff orthosis does
at loading: the spring resists the fast plantarflexion after heel strike
(up to 33 N m), the foot slap index halves (452 deg/s, below healthy) and the
foot lands flat. Its toe clearance is the same as without a device and the
steppage only slightly smaller (swing hip flexion 53.4 against 56.6 degrees,
knee 80.0 against 78.5). It also stores energy as the ankle dorsiflexes in stance (up to
27 N m plantarflexing) and returns it at push-off, 12 J per stride each way,
so the total push-off peak rises to 209 W while the muscles' own peak falls
by 9%. The hypothesis expected a passive AFO to resist push-off; with a
neutral angle of 0 a spring of this stiffness helps the first half of
push-off and resists only the late plantarflexion. Part 3 would also fail on
the muscle power alone (113 W, above 105.5 W).

**Active AFO (10 degree swing target).** It holds the foot up from toe-off
(5 to 10 N m in swing) and through contact (+3.7 degrees at initial
contact), with 13.5 N m peaks at the actuator limit. Toe clearance is the
same as without a device, but the model gets it differently: the swing hip
flexion falls from 56.6 to 50.0 degrees and the knee to its healthy value,
and the cost of transport falls by 5% (5.94 to 5.63 J/(kg m), healthy 5.46).
With the active AFO the re-optimized controller drops most of the steppage
compensation, and push-off is unchanged. Foot slap is not reduced (833 deg/s):
the braking phase is short and limited by the actuator. The device works
about 4 J per stride each way.
