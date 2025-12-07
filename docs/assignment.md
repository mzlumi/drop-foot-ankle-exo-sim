# Project 1: An IMU-Driven Ankle Exoskeleton for Drop-Foot Gait, in Simulation

**Type:** independent course-style project (simulation only, no hardware)
**Length:** 6 weeks at about 10 hours per week
**Tools:** SCONE (free, Windows/macOS/Linux), Python (NumPy, SciPy, pandas, Matplotlib), Git
**Adapted from:** CMU 16-868 Biomechanics and Motor Control (drop-foot reflex-model project), Georgia Tech ME 6409 Biomechatronics of Wearable Robotic Devices (hypothesis-driven device simulation), Utah ME EN 7960 Wearable Robotics (HW1 actuator sizing, HW3 torque control), Stanford BIOE/ME 485 Lab 1 (simulated AFO design), Notre Dame AME 60553 Wearable Robotics (phase-based exoskeleton control). Links are at the end.

---

## 1. Background

Drop foot is weakness of the ankle dorsiflexors, mainly tibialis anterior (TA). It appears after stroke, in cerebral palsy, in multiple sclerosis and after peroneal nerve injury. Two problems follow:

1. **In swing**, the foot cannot be lifted, so toe clearance drops and the toes catch the ground. Patients compensate with extra hip and knee flexion (steppage gait) or hip circumduction.
2. **At heel strike**, the foot cannot be lowered under control, so it slaps the ground.

The standard clinical answer is a passive ankle-foot orthosis (AFO). This is a spring that holds the foot near neutral, but it also resists the plantarflexion needed for push-off. Active AFOs (Blaya and Herr 2004) change their impedance across the gait cycle, so they help in swing and early stance and stay out of the way in late stance. To do that, the device must know which gait phase the wearer is in, and most devices estimate it from a shank-mounted IMU.

In this project you will build that whole chain in a neuromusculoskeletal simulation:

- a reflex-controlled walking model;
- a drop-foot version of it;
- an actuator sized from gait data;
- a simulated shank IMU that detects gait events;
- a phase-based exoskeleton controller;
- a hypothesis-driven comparison against no device and a passive AFO.

## 2. Learning objectives

By the end you should be able to:

- run and optimize a muscle-reflex walking model (Geyer and Herr 2010) and validate its gait against normative data;
- model a neuromuscular impairment by changing muscle parameters, and quantify the resulting gait deviations with clinical metrics;
- size a series elastic actuator (motor, gear ratio, spring) from joint torque and angle trajectories;
- design a gait-event detector from noisy, delayed shank gyroscope data;
- implement and tune a finite-state impedance controller for an ankle exoskeleton;
- design and analyze a low-level SEA torque controller (bandwidth, saturation);
- state a hypothesis before running an experiment, and report results with variability across optimization seeds.

## 3. Setup (Part 0, not graded)

1. Install SCONE from <https://scone.software> (download page, macOS build). The built-in OpenSim 3 engine is enough. Hyfydy, the faster commercial engine, is optional.
2. Open the bundled tutorials (`Scenarios/Tutorials`) and run:
   - `Tutorial 4a - Gait.scone`, which uses the `Human0914` model with `ControllerGH2010.scone` and `MeasureGait05.scone`;
   - `Tutorial 5a - Pathological Gait - Weak Plantarflexors.scone`, which shows how to override `max_isometric_force` per muscle;
   - `Tutorial 6b - Script - Balance Device.scone`, which applies a device moment from a Lua `ScriptController`.
3. Read `data/ScriptControllerBalanceDevice.lua`. You will use these Lua calls: `model:find_body`, `model:find_dof`, `body:ang_vel()`, `body:ang_pos()`, `body:contact_force()`, `dof:position()`, `dof:velocity()`, `body:add_external_moment(x, y, z)`, `model:time()` and `model:delta_time()`.
4. Make a Git repository with this layout:

```
ankle-exo-dropfoot/
  scenarios/        # .scone files, one per condition
  scripts/          # Lua controllers and measures
  analysis/         # Python: load .sto results, metrics, figures
  actuator/         # Python: actuator sizing and torque control (Parts C and E)
  results/          # optimized .par files and exported .sto (small ones only)
  figures/
  report/
  README.md
```

**Model facts.** `Human0914` is planar, with 7 muscles per leg: `hamstrings`, `glut_max`, `iliopsoas`, `vasti`, `gastroc`, `soleus` and `tib_ant`, each with `_r` and `_l` suffixes. The joints are `hip_flexion`, `knee_angle` and `ankle_angle`, and the bodies include `tibia`, `talus`, `calcn` and `toes`. Before you write any controller, check the sign of `ankle_angle` by plotting a healthy stride. In OpenSim gait models, positive usually means dorsiflexion.

## 4. Tasks

### Part A: Healthy baseline (10 points)

A1. Optimize healthy gait at about 1.2 m/s. Start from the tutorial result file (for example `ResultGait10.par`) to save time. Run **at least 3 optimizations with different random seeds** and keep all of them.

A2. Export 10 s of walking. In Python, segment the data into strides using heel-strike events from foot contact force (threshold about 5% body weight). Compute the mean ± SD across strides of hip, knee and ankle angles, ankle moment and vertical ground reaction force, all normalized to 0-100% of the gait cycle.

A3. Compare your curves against normative adult data. Use Winter's *Biomechanics and Motor Control of Human Movement* tables, or the Camargo et al. 2021 open dataset (level walking, matching speed). Report the RMSE and Pearson r for each joint angle. Also say in one paragraph where the model differs and why. For example, the model has no subtalar joint, is planar and has no arms.

**Deliverable:** a figure of model vs normative curves (3 angles, ankle moment, vertical GRF) and a table of RMSE and r.

### Part B: A drop-foot model (15 points)

B1. Create **unilateral** right-side drop foot by scaling `tib_ant_r` `max_isometric_force` to 50%, 25% and 10% of healthy. Use the asymmetric controller (`ControllerGH2010asym.scone`) so that each side can adapt independently.

B2. For each weakness level, run two cases:
- **(i) immediate effect:** simulate with the healthy controller parameters unchanged;
- **(ii) adapted gait:** re-optimize the controller (3 seeds each).

Case (ii) is the model's version of patient compensation.

B3. Compute these clinical metrics for the affected side. Define each one precisely in your report.

| Metric | Definition |
|---|---|
| Minimum toe clearance | Minimum vertical height of the toes body origin during mid-swing, in mm |
| Ankle angle at initial contact | Degrees, at the heel-strike event |
| Peak swing dorsiflexion | Degrees |
| Foot-slap index | Peak plantarflexion angular velocity in the 0-15% of the gait cycle after heel strike, in deg/s |
| Steppage compensation | Peak hip flexion and peak knee flexion in swing, as a change from healthy |
| Asymmetry | Step length and stance time symmetry index between left and right |
| Cost of transport | From the `EffortMeasure` (Wang 2012 model) per unit distance |

B4. If the model falls at 10% strength, report that as a result. Then find the weakest level that still walks by bisection on the force scale.

**Deliverable:** a metrics table across weakness levels for immediate and adapted gait, and an overlay plot of affected-side ankle and hip angles. Write one paragraph comparing these with the clinical features of drop foot. Do you see steppage? Foot slap?

### Part C: Size the exoskeleton actuator (15 points)

You are designing a unilateral ankle exoskeleton built from a brushless DC motor, a gear reduction with ratio N, and a series spring with stiffness k between the gearbox output and the ankle.

C1. **Torque requirement.** From your simulations, derive a target assistive torque profile over the gait cycle. Use the swing dorsiflexion torque and early-stance plantarflexion braking torque that the missing TA strength would have produced (healthy TA moment minus weak TA moment), plus a 20% margin.

C2. **Actuator model.** Write the actuator equations:
- motor: torque τ_m = K_t·i and voltage V = R·i + K_e·ω_m;
- reflected inertia: J_m·N²;
- spring: τ = k·(θ_out − θ_joint).

For a given joint torque and joint angle trajectory, compute the motor angle, speed and current needed. Then compute the electrical energy per stride, as the integral of max(V·i, 0) plus I²R losses (state your regeneration assumption). Also compute peak motor speed, peak current and peak voltage.

C3. **Design sweep.** Choose one real motor from a manufacturer datasheet (any frameless or geared brushless DC motor sized for wearables) and use its K_t, R, J_m, rated current and maximum speed. Sweep N from 20 to 150 and k from 50 to 2000 N·m/rad, plus the rigid case. Plot energy per stride on the (N, k) grid with the regions that violate the speed, current or voltage limits masked out.

C4. Pick a design. Explain why a series spring can lower energy and peak power for this torque profile (Au and Herr 2008), and when it does not help. Note that a dorsiflexion-assist profile is very different from a push-off profile.

**Deliverable:** the (N, k) heat map with constraints, the chosen design with its numbers, and the motor torque-speed operating points over one stride drawn on the motor's torque-speed envelope.

### Part D: Simulated IMU and gait-event detection (15 points)

Your exoskeleton will not have access to the simulator's contact forces. It has one IMU on the right shank.

D1. In a Lua `ScriptController`, read `tibia_r` sagittal angular velocity (`ang_vel().z`) every step and turn it into a realistic gyroscope signal:
- sample at 100 Hz (hold the value between samples);
- add white noise of about 0.5 deg/s RMS;
- add a constant bias of a few deg/s;
- add a 10-20 ms transport delay.

Log both the true and the measured signal (use `store_data` in the script).

D2. Implement a real-time gait-event detector that uses only the measured gyro. Use the classic shank-gyro features: a large positive mid-swing peak, then a zero crossing and negative minimum around heel strike, then a negative minimum around toe-off (check the signs against your own data). It must be causal: no future samples and no offline filtering. Estimate gait phase as time since heel strike divided by the running average stride time.

D3. Validate against ground truth taken from contact forces. Report the heel-strike and toe-off timing error (mean ± SD, in ms) and the missed and false detection rates across at least 50 strides. Do this for healthy gait and for the adapted drop-foot gait from B2 (ii), because the shank pattern changes when the foot drops.

**Deliverable:** an annotated gyro trace with detected events, and a timing-error table for both gait types.

### Part E: Low-level SEA torque control (10 points)

This part is done offline in Python, using the actuator you chose in C4.

E1. Model the SEA as motor inertia plus damping, the gear, the spring, and a joint whose position is given by the simulated ankle trajectory. Design a torque controller: PID on spring-deflection torque, plus feedforward. Optionally add a disturbance observer (Vallery et al. 2007; Paine et al. 2014).

E2. Report the closed-loop small-signal torque bandwidth from a Bode plot of the linearized model. Also simulate large-signal tracking of the Part C torque profile with current and voltage saturation. Aim for a bandwidth of at least 10 Hz and an RMS tracking error under 10% of peak torque. If you cannot reach that, explain the trade-off.

E3. Fit the closed-loop torque response to a low-order model, for example first order with time constant τ_c plus a pure delay. Use this model in Part F so that the device in SCONE cannot apply torque instantly.

**Deliverable:** a Bode plot, a tracking plot and the fitted actuator model parameters.

### Part F: Exoskeleton controllers and the experiment (25 points)

F1. **Passive AFO baseline.** Implement a rotational spring around a neutral ankle angle as a pair of equal and opposite external moments on `tibia_r` and `talus_r`: τ = −k_AFO·(θ − θ_0). Sweep k_AFO and pick the best one by your primary metric. This is the clinical standard you have to beat.

F2. **Phase-based active controller.** Build a finite-state machine driven only by your Part D detector:

| State | Behaviour |
|---|---|
| Early stance (heel strike to about 15% of the gait cycle) | Viscous plantarflexion braking, to remove foot slap |
| Mid and late stance | Zero torque (transparent), so push-off is not blocked |
| Swing | PD position control of the ankle toward a dorsiflexed target |

Pass the commanded torque through your Part E actuator model and clip it to the Part C torque limit.

F3. **Hypothesis first.** Write your hypothesis and your primary metric in the README and commit it *before* you run the comparison. Example: "At 25% TA strength, the phase-based active AFO restores minimum toe clearance to within 10 mm of healthy without reducing peak ankle push-off power, while the best passive AFO reduces push-off power by more than 15%."

F4. **Conditions:**
- healthy;
- drop foot with no device;
- drop foot with the passive AFO;
- drop foot with the active AFO.

Run each device condition two ways: **(a)** with the drop-foot controller parameters frozen, which is like the first day of wearing the device, and **(b)** after re-optimizing the reflex parameters with the device on, which is like adaptation. Use 3 seeds per condition.

F5. **Robustness:**
- **Speed:** test at least two walking speeds (`MeasureGait10` and `MeasureGait15` set different minimum speeds).
- **IMU noise:** double the noise and the delay.
- **Perturbation:** add one push or trip in the style of `Tutorial 4c - Perturbed Gait.scone`.

Report which device degrades more.

**Deliverable:** a results figure with all conditions on the metrics from B3, plus device energy per stride and peak device power. Write one paragraph per condition, and give a clear verdict on the hypothesis.

### Part G: Report and repository (10 points)

- **Report:** 6-8 pages in IEEE conference format (Introduction, Methods, Results, Discussion, Limitations). The limitations must cover the planar model, a reflex controller that is not a real patient, the idealized attachment (no strap compliance or misalignment), and optimizer randomness.
- **README:** one figure at the top, then a 3-sentence summary, then how to reproduce everything. Each figure must be regenerated by one command (for example `python analysis/make_figures.py`).
- **Media:** a short GIF or video of the three drop-foot conditions side by side (SCONE can export video).
- **Repository hygiene:** the optimized `.par` files are committed, so every result can be re-run without re-optimizing.

## 5. Grading rubric (100 points)

| Part | Points | Full marks require |
|---|---|---|
| A Healthy baseline | 10 | 3 seeds, a stride-averaged comparison against normative data, error metrics |
| B Drop-foot model | 15 | All metrics precisely defined, immediate vs adapted gait, clinical interpretation |
| C Actuator sizing | 15 | Correct motor model, constrained (N, k) sweep, justified design |
| D IMU event detection | 15 | Causal detector, ground-truth validation on both gait types |
| E Torque control | 10 | Bandwidth and saturation analysis, fitted model used in Part F |
| F Experiment | 25 | Hypothesis committed first, all conditions × 2 adaptation modes × 3 seeds, robustness tests |
| G Report and repository | 10 | Reproducible figures, honest limitations, clear README |

## 6. Hints and pitfalls

- **External moments in scripts persist.** In the Tutorial 6b device script, a moment stays applied until the script adds the opposite moment. Keep track of the moment you applied on the previous step, and add only the change each step. Check this with a constant-torque test before you trust any result.
- **Apply joint torques as action-reaction pairs**, with +τ on `talus_r` and −τ on `tibia_r`. Otherwise you are pushing the whole body around.
- **CMA-ES is random.** Never compare two single runs. Report the mean and spread across seeds, and let the optimizer run to convergence (look at the cost curve).
- **Runtime:** a gait optimization can take tens of minutes to hours. Use all CPU cores (SCONE runs evaluations in parallel), and start from existing `.par` files.
- **Falling is data.** If a condition makes the model fall, count it as a failure and report it. Do not tune until everything walks.
- **Units and signs:** decide the dorsiflexion sign once, write it at the top of every script, and plot every new signal before using it.

## 7. Going further (optional, for the portfolio)

1. **Human-in-the-loop optimization in silico.** Wrap the active controller gains in an outer CMA-ES loop that minimizes the model's metabolic cost, and compare the result with the hand-tuned gains (compare with Zhang et al. 2017).
2. **Learned phase estimation.** Train a small temporal convolutional network to predict continuous gait phase from the simulated gyro. Then test it on real shank IMU data from the Camargo et al. 2021 dataset without retraining, and report the sim-to-real gap.
3. **Your own data.** Run the Part D detector offline on shank IMU recordings from your own motion lab sessions, and compare it against Vicon or force-plate events.
4. **3D.** Repeat Part F with the 3D H1922 model in SCONE (Hyfydy recommended for speed).
5. **Clinical realism.** Add mild soleus hyper-reflexia, as in `Tutorial 5c`, to the drop-foot model to imitate a spastic gait pattern such as cerebral palsy, and test whether the active controller still helps.

## 8. References

1. H. Geyer and H. Herr, "A muscle-reflex model that encodes principles of legged mechanics produces human walking dynamics and muscle activities," *IEEE TNSRE*, 2010.
2. T. Geijtenbeek, "SCONE: Open source software for predictive simulation of biological motion," *Journal of Open Source Software*, 2019. <https://scone.software>
3. J. A. Blaya and H. Herr, "Adaptive control of a variable-impedance ankle-foot orthosis to assist drop-foot gait," *IEEE TNSRE*, 2004.
4. S. K. Au and H. Herr, "Powered ankle-foot prosthesis," *IEEE Robotics and Automation Magazine*, 2008.
5. H. Vallery et al., "Compliant actuation of rehabilitation robots," *IEEE Robotics and Automation Magazine*, 2008; and H. Vallery et al., "Passive and accurate torque control of series elastic actuators," *IROS*, 2007.
6. N. Paine, S. Oh and L. Sentis, "Design and control considerations for high-performance series elastic actuators," *IEEE/ASME Transactions on Mechatronics*, 2014.
7. A. D. Robertson and G. S. Sawicki, "Exploiting elasticity: Modeling the influence of neural control on mechanics and energetics of ankle muscle-tendons during human hopping," *Journal of Theoretical Biology*, 2014.
8. J. Camargo et al., "A comprehensive, open-source dataset of lower limb biomechanics in multiple conditions of stairs, ramps, and level-ground ambulation and transitions," *Journal of Biomechanics*, 2021. <https://www.epic.gatech.edu/opensource-biomechanics-camargo-et-al/>
9. J. Zhang et al., "Human-in-the-loop optimization of exoskeleton assistance during walking," *Science*, 2017.
10. D. A. Winter, *Biomechanics and Motor Control of Human Movement*, 4th ed., Wiley, 2009.

## 9. Source courses

| Course | What this project takes from it |
|---|---|
| CMU 16-868 Biomechanics and Motor Control (Geyer) | Drop-foot study with the Geyer-Herr reflex model ([past student write-up](https://www.michaeldermksian.com/biomechanics-walker/), [course page](https://sites.google.com/andrew.cmu.edu/ri-lsg/teaching-16-868)) |
| Georgia Tech ME 6409 Biomechatronics of Wearable Robotic Devices (Sawicki) | Hypothesis-driven wearable-device simulation as the final project ([syllabus](https://syllabus.gatech.edu/sites/default/files/2026-04/Wearable%20Robotics%20Fall%202026%20USG%20Syllabus.pdf)) |
| Utah ME EN 7960 Wearable Robotics (Lenzi) | HW1 SEA sizing for an ankle device, HW3 closed-loop SEA torque control ([syllabus](https://rmcoeh.com/images/pdfs-doc/courses-syllabi/MEEN%207960%20Syllabus.pdf)) |
| Stanford BIOE/ME 485 Modeling and Simulation of Human Movement | Lab 1, simulation-based AFO design for ankle injury ([lab](https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53088618)) |
| Notre Dame AME 60553 Wearable Robotics | Phase-variable and finite-state control of lower-limb wearable robots ([course notes](https://werolab.nd.edu/teaching/wr/)) |
