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

## Sim to real: Camargo et al. (2021), 20 subjects at 1.2 m/s

`python analysis/part_d_camargo.py`. The calibrated shank gyroscope of each
subject (sign and clock offset against motion capture; AB10 and AB13 rejected
by the calibration) at 100 Hz plus the simulation's 15 ms delay, with the
detector settings tuned on the simulation and not changed. Scored on the
1.2 m/s plateaus against the right belt force. Per-subject statistics in
`camargo.csv` (no signals), pooled in `camargo_pooled.csv`, figure
`figures/detector_sim_vs_real.png`.

| HS feature | HS missed / false (of 536) | HS error (ms) | HS latency (ms) | TO missed / false (of 532) | TO error (ms) | TO latency (ms) |
|---|---|---|---|---|---|---|
| min | 1 / 1 | +12.4 +/- 20.6 | 29.7 | 5 / 5 | -40.8 +/- 26.1 | -14.0 |
| zero | 1 / 1 | -31.9 +/- 10.8 | -27.0 | 6 / 6 | -40.8 +/- 26.1 | -13.9 |

The detector transfers without retuning: 99.8% of heel strikes and 99% of
toe-offs are found (the 5 missed toe-offs are all in AB09). What changes:

* **Heel strike with `min` is bimodal on real data.** Most subjects have a
  shallow notch at contact, as the model does, and the error is near 0 ms;
  in AB06 and AB16 (the two subjects whose gyroscope axis has the opposite
  sign, so probably mounted differently) there is no notch and the detector
  waits for the impact minimum, +50 ms. Seven subjects mix both (SD above
  15 ms). The `zero` feature has no such ambiguity and half the spread on
  real data, while in simulation it was the other way round. The controller
  keeps `min`, as decided on simulated data; the report discusses the
  trade-off, and the delay robustness test (Part F5) covers a 50 ms later
  heel strike.
* **Toe-off is estimated earlier and with more spread** (-41 +/- 26 ms
  against -13 +/- 3 ms): the pre-swing minimum of the real shank velocity
  comes 15 to 65 ms before the belt force reaches 5% of body weight,
  depending on the subject.
* The simulated error distributions are narrow because all strides of one
  model are nearly identical; between-subject variation is the dominant
  source of error in the real data.
