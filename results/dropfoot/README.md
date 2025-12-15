# Drop foot (Part B)

Right tibialis anterior weakened by scaling its maximum isometric force
(`tib_ant_r.max_isometric_force.factor`), asymmetric reflex controller.

## Immediate effect (no re-optimization)

`python analysis/part_b_immediate.py`: each seed's healthy controller,
written once per side (`healthy_asym.par`), evaluated with the weak muscle.
Rows in `immediate.csv`, bracket in `immediate_threshold.csv`.

**The healthy controller falls at every strength from 10% to 90%, for all
three seeds.** The weakest strength at which it still walks 10 s is between
96.3 and 96.9% (seed 1), 98.1 and 98.8% (seed 2) and 97.5 and 98.1% (seed 3).
Below about 90% the model falls within 1.3 to 1.6 s, in the first or second
stride; at 90 to 97% it falls later (2 to 9.4 s).

Mechanism, checked for seed 1: at 50% strength the right foot touches the
ground 0.20 s after toe-off, in early swing (healthy swing lasts 0.54 s), the
model trips and falls at 1.5 s. At 90% the first swing clears and a later one
fails. The healthy controller is an effort optimum with no margin: peak
swing activation of tibialis anterior is only 0.15, mid-swing toe clearance is
36 mm, and the same gait already fell after a 2 N m plantarflexing pulse of
50 ms in swing (`results/device_check`). This is a property of the optimized
model, not of human gait: people walk with reserve and adapt within a few
steps. It is why the drop-foot comparison uses re-optimized (adapted)
controllers, and why immediate-effect metrics cannot be computed (no complete
strides after the start-up).

## Adapted gait (re-optimized asymmetric controller)

`python analysis/curate_runs.py dropfoot_ta<x>` for 50, 25 and 10%, then
`python analysis/part_b_adapted.py`. Each seed starts from its healthy
controller written once per side and runs 150 generations; seeds that had
not converged then (best cost better by 1% or more over the last 40
generations) were continued from their best `.par` until they had. The
histories of the earlier stages are kept as `history_stage<i>.txt` next to
each `best.par`.

| Strength | Seed 1 | Seed 2 | Seed 3 |
|---|---|---|---|
| 50% | 0.603 (2 stages, 300 generations; 1.3% over the last 40, not converged) | 0.700 (150) | 0.543 (150) |
| 25% | 0.596 (2 stages, 230) | 0.695 (2 stages, 260) | 0.590 (2 stages, 280) |
| 10% | 0.589 (3 stages, 400) | 0.563 (2 stages, 300) | 0.563 (3 stages, 410) |

Best costs (healthy: 0.545 to 0.547). Seed 1 at 50% ended its second stage at 1.3%
improvement over the last 40 generations, just above the criterion, and is
reported as it is. The 10% seeds needed the
most generations: at 150 generations only seed 2 walked (seed 1 cost 7.5,
seed 3 cost 24); with more generations all three found walking gaits with
costs as low as the 25% ones. Seed 2 at 50% and 25% settled in a worse
optimum than the other two seeds (cost 0.70). The cost does not order the
strengths: how long a seed searched and which optimum it found matter as
much as the weakness. **The adapted model walks at every tested strength**,
so the bisection between a walking and a falling adapted level was not
needed.

Metrics on the right side, mean +/- SD over seeds (all walk), from
`metrics_table.md`; per run in `adapted.csv`, curves in `curves.csv` and
`figures/dropfoot_overlay.png`:

| Metric | Healthy | 50% | 25% | 10% |
|---|---|---|---|---|
| Min toe clearance, mid swing (mm) | 36.3 +/- 0.3 | 45.5 +/- 1.5 | 56.5 +/- 4.9 | 49.9 +/- 8.9 |
| Ankle at initial contact (deg) | 0.4 +/- 0.3 | -2.8 +/- 5.0 | -6.8 +/- 2.5 | -8.7 +/- 4.9 |
| Peak swing dorsiflexion (deg) | 0.4 +/- 0.3 | -2.8 +/- 5.0 | -6.7 +/- 2.5 | -5.7 +/- 6.5 |
| Foot slap index (deg/s) | 782 +/- 5 | 871 +/- 71 | 824 +/- 31 | 844 +/- 117 |
| Steppage, hip (deg) | 0 | +6.0 +/- 2.7 | +10.9 +/- 0.9 | +9.7 +/- 1.4 |
| Steppage, knee (deg) | 0 | +3.0 +/- 1.7 | +4.1 +/- 1.6 | +2.9 +/- 2.6 |
| Peak ankle push-off power (W) | 126 +/- 1 | 132 +/- 2 | 124 +/- 4 | 122 +/- 9 |
| Speed (m/s) | 1.16 +/- 0.01 | 1.23 +/- 0.05 | 1.28 +/- 0.03 | 1.20 +/- 0.06 |
| Stride time (s), length (m) | 1.36, 1.57 | 1.39, 1.71 | 1.38, 1.77 | 1.37, 1.64 |
| Cost of transport (J/(kg m)) | 5.46 +/- 0.01 | 5.87 +/- 0.39 | 6.05 +/- 0.21 | 5.71 +/- 0.15 |

What the adapted model does:

* **The foot drops and the leg lifts it clear.** The ankle no longer reaches
  neutral in swing (peak swing dorsiflexion -3 to -7 degrees, the ankle
  hangs 15 to 30 degrees plantarflexed in mid swing) and lands plantarflexed
  (-3 to -9 degrees at initial contact, a flat or toe-first contact). The
  controller compensates mainly at the hip (+6 to +11 degrees of swing hip
  flexion) and less at the knee (+3 to +4 degrees): a steppage gait.
* **Toe clearance goes up, not down.** The compensation overshoots, and
  mid-swing toe clearance is 9 to 20 mm above healthy at every strength.
  The device is therefore not needed to avoid tripping once the model has
  adapted; it can only replace the compensation. This matters for the
  hypothesis, whose first part asks for toe clearance within 10 mm of healthy.
* **The weak muscle works harder.** Swing activation of tibialis anterior
  rises from 0.15 (healthy) to about 0.2, 0.45 and 0.6 at 50, 25 and 10%.
* **Foot slap is mild in this model.** The healthy model already drops its
  foot at 782 deg/s after heel strike; drop foot raises the index by 5 to
  11%, with a large spread at 10%.
* **Effort.** The cost of transport rises by 5 to 11%. Push-off power is
  unchanged within the seed spread.
* **Symmetry.** Step length and stance time differ between the legs by up to
  6% and 2%, about one seed SD, with signs that change between seeds
  (`metrics_table.md`).

**Against the CMU 16-868 project.** That project's 2D Geyer and Herr model
at 33% tibialis anterior strength walked with a 1.01 m stride in 1.64 s
(0.65 m/s), within one SD of drop-foot patient data, and raised its knee more
than patients do. Here the stride is longer and faster (1.77 m in 1.38 s at
25%), because the gait measure penalizes walking more than 5% below 1.2 m/s,
while their cost let the model slow down as patients do. Both models show the
exaggerated swing lift; here most of it is at the hip. The numbers are from
the project's public report and are a qualitative reference only, since the
models, objectives and strengths differ.
