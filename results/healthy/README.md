# Healthy optimizations (Part A)

Scenario `scenarios/healthy.scone`, CMA-ES seeds 1, 2 and 3, warm start from
the tutorial result `ResultGait10.par`. Curated with
`python analysis/curate_runs.py healthy --asym`.

The runs were planned for 150 generations and stopped at generation 119 by
hand. The best cost had already reached about 0.549 by generation 10 and then
improved by less than 0.5% (0.18%, 0.00% and 0.18% over the last 40
generations), which meets the convergence criterion in `dropfoot.runs`. The
decision was made from the cost history only, before any gait metric of these
runs was looked at.

| seed | best cost | generation of best |
|---|---|---|
| 1 | 0.546 | 118 |
| 2 | 0.547 | 123 |
| 3 | 0.545 | 113 |

Costs are as rounded in SCONE's file names; exact values come from
re-evaluation (`summary.csv`: 0.54588, 0.54671 and 0.54465). Each `seed<i>/` folder has `best.par`, `history.txt`, the
run's `config.scone`, `run.json`, and `healthy_asym.par` (the same parameters
written once per side for the asymmetric controller, the warm start of the
drop-foot runs).

## Comparison with normative walking

`python analysis/part_a.py` evaluates the three results and compares them with
the Camargo et al. (2021) curves at 1.2 m/s: table in `vs_normative.md`,
figure `figures/healthy_vs_normative.png`. All three seeds walk the full 10 s.
Each seed gives 4 complete right strides after the two start-up strides, 12
in total; the seeds are nearly identical (seed ranges in the table), because
they share the warm start and converge to the same gait.

What agrees: the shapes of the ankle moment (r 0.95, peak plantarflexion
moment about 1.65 N m/kg against 1.55), the vertical ground reaction force
(r 0.95) and the shank angular velocity (r 0.96, swing peak about 400 deg/s
at 86% of the cycle in both), which is the signal the event detector uses.
Stance lasts 61.7% of the cycle against 60.3 +/- 1.0%.

What does not:

* **Hip offset.** Model hip flexion is 19 deg above the data over the whole
  cycle with the right shape (r 0.97, RMSE 7 deg without the offset). Hip
  angles are relative to the pelvis, and the model walks with its pelvis
  tilted forward by 13 deg on average (`pelvis_tilt` -12.9 deg, range -15 to
  -9.5 deg), which explains most of it.
* **Stiff stance knee.** The knee extends fully in mid and late stance
  (0 deg from 35 to 50% of the cycle against about 11 deg) and flexes late
  before toe-off; swing flexion peaks at 76 deg against 68 deg.
* **Fast plantarflexion after heel strike.** The ankle drops from 0 to -20 deg
  in the first 3% of the cycle (normative: about 0 deg), with a peak
  plantarflexion velocity of about 780 deg/s and a 1.55 BW impact peak in the
  vertical force. The healthy model already has little eccentric control of
  the foot at loading, so the foot slap index of the drop-foot runs is judged
  against this model value, not against human data.
* **Less dorsiflexion.** The ankle reaches 14 deg in late stance (21 deg in the
  data) and stays a few degrees plantarflexed in swing. Part of the 5.7 deg
  offset is the neutral angle of the two models; the RMSE without it is
  4.7 deg.
* **Speed.** The gait measure penalizes only speeds more than 5% below
  1.2 m/s, and the optimizer settles just above that limit, at 1.15 to
  1.17 m/s. The normative curves are at 1.2 m/s.

The minimum toe clearance in mid swing is 36 mm (toes body origin, see
`dropfoot.metrics`).
