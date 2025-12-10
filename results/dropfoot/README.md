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
