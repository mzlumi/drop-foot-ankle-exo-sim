# Healthy model versus normative walking at 1.2 m/s

Model: mean of the mean right strides of seeds 1, 2, 3 (12 strides). Normative: 22 subjects, 568 strides, Camargo et al. (2021). RMSE and r compare the two mean curves over 0 to 100% of the gait cycle; ranges in brackets are over seeds. The offset is the model minus normative mean; the last column is the RMSE after removing it. The normative SD is the between-subject SD averaged over the cycle, for scale.

| variable | unit | RMSE | RMSE without offset | offset | r | normative SD |
|---|---|---|---|---|---|---|
| hip_flexion | deg | 20.2 [19.9, 20.4] | 7.13 | +18.9 | 0.97 [0.97, 0.98] | 7.38 |
| knee_flexion | deg | 10.1 [10.1, 10.2] | 8.29 | -5.82 | 0.96 [0.95, 0.96] | 4.42 |
| ankle_angle | deg | 7.4 [7.32, 7.55] | 4.66 | -5.74 | 0.83 [0.82, 0.84] | 2.97 |
| ankle_moment | N m/kg | 0.174 [0.168, 0.178] | 0.174 | +0.00267 | 0.95 [0.95, 0.96] | 0.101 |
| vertical_grf | BW | 0.145 [0.14, 0.15] | 0.145 | -0.00991 | 0.95 [0.95, 0.95] | 0.0425 |
| shank_gyro | deg/s | 49 [49, 49.1] | 49 | +0.475 | 0.96 [0.96, 0.96] | 21.6 |

Stance: model 61.7% (seeds 61.5 to 61.8%), normative 60.3 +/- 1.0%.
Speed: 1.160 m/s (seeds 1.153 to 1.166). Cost of transport: 5.457 J/(kg m).

Source of the normative data: Camargo J, Ramanathan A, Flanagan W, Young A (2021). A comprehensive, open-source dataset of lower limb biomechanics in multiple conditions of stairs, ramps, and level-ground ambulation and transitions. Journal of Biomechanics 119:110320. doi:10.1016/j.jbiomech.2021.110320. Data CC BY 4.0.
