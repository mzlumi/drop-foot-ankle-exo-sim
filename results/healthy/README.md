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
re-evaluation. Each `seed<i>/` folder has `best.par`, `history.txt`, the
run's `config.scone`, `run.json`, and `healthy_asym.par` (the same parameters
written once per side for the asymmetric controller, the warm start of the
drop-foot runs).
