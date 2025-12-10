# Gait-event detector validation (Part D3)

`python analysis/part_d_validation.py [--dropfoot <factor>]`. Each run is a
60 s simulation with the simulated shank gyroscope (100 Hz, 0.5 deg/s noise,
2 deg/s bias, 15 ms delay). Ground truth is the right foot's vertical force
crossing 5% of body weight. Scores (see `dropfoot.validation`) are over 2 s to
the end minus 0.5 s; errors are estimate minus truth, latency is the time the
event was confirmed minus truth. Per run in `validation.csv`, pooled over
seeds in `pooled.csv`, annotated trace in `figures/detector_trace.png`.

The Python twin, run on the logged measured samples, reproduces the events the
Lua detector logged during every simulation (largest difference 7e-15 s).

## Healthy gait, 3 seeds, 127 heel strikes and 129 toe-offs

| HS feature | HS missed / false | HS error (ms) | HS latency (ms) | TO missed / false | TO error (ms) | TO latency (ms) | phase error mean / RMS (% cycle) |
|---|---|---|---|---|---|---|---|
| min | 0 / 0 | +25.4 +/- 2.9 | 37.8 | 0 / 0 | -13.0 +/- 3.0 | 10.0 | -1.5 / 2.4 |
| zero | 0 / 0 | -50.6 +/- 1.4 | -45.6 | 0 / 0 | -13.0 +/- 3.0 | 10.0 | +4.1 / 4.4 |

Both features find every event. The `zero` feature fires at the zero
crossing of the shank velocity in terminal swing, about 50 ms *before* foot
contact, so it is confirmed before the event happens. The `min` feature
confirms a shallow notch (about -90 deg/s) at contact, before the deeper
impact minimum, 25 ms after the force event. Toe-off is the pre-swing minimum
and is estimated 13 ms early.

Feature choice: by the rule fixed in the script before the results were seen
(no missed or false events, then the lower pooled HS mean absolute error), the
controller uses `min` (`chosen_feature.txt`). The choice is revisited only
with the drop-foot gait added, on simulated data, never on the Camargo data.
