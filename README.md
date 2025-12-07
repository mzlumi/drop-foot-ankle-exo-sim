# Drop-Foot Gait and an IMU-Triggered Ankle Exoskeleton in a Neuromuscular Simulation

A reflex-controlled walking model (Geyer and Herr 2010, in SCONE) is given unilateral drop foot by weakening tibialis anterior. An ankle exoskeleton is then sized, given a low-level torque controller, and triggered by gait events detected from a simulated shank gyroscope with realistic noise, bias and delay. The project tests a stated hypothesis by comparing no device, a passive ankle-foot orthosis (AFO) and a phase-based active AFO, across several optimization seeds and with and without the model adapting to the device.

The full specification is [`docs/assignment.md`](docs/assignment.md). It combines tasks from the five courses below into one project.

**Related repositories.** [scone-pathological-gait](https://github.com/mzlumi/scone-pathological-gait) is the companion repository: the EPFL BIOENG-404 SCONE assignment (healthy gait, heel walking from plantarflexor weakness, toe walking from hyperreflexia, crouch gait). This project reuses its headless SCONE runner and gait analysis code instead of copying them. This repository covers a different impairment (dorsiflexor weakness) and adds what that one does not have: a device, its actuator, an IMU event detector and a controlled experiment. The event detector pairs with [imu-locomotion-gait-phase](https://github.com/mzlumi/imu-locomotion-gait-phase) (gait phase from real wearable IMUs), and the sensor error model with [imu-opensim-validation](https://github.com/mzlumi/imu-opensim-validation) (IMU kinematics against optical motion capture).

## Adapted from

### CMU 16-868, Carnegie Mellon University

- **Course.** 16-868, taught by Prof. Hartmut Geyer (Legged Systems Group, Robotics Institute). The current course page titles it "Legged Systems" (fall semester, 12 units, graduate elective). The past student report below calls it "Biomechanics & Motor Control".
- **What the course covers.** Modeling, analysis and control of legged locomotion, from simple gait models (compass gait, linear inverted pendulum, spring-mass) through segmented legs to the human system (Hill-type muscles, reflexes, neuromuscular gait models) and to exoskeletons and prostheses (impedance, phase-based and virtual neuromuscular control). Coding is in MATLAB Simulink with starter code. Four to five assignments (67%) and a final project on "a legged mobility problem of their own choosing" (33%).
- **The original task.** A past final project (Dermksian, Mitchell, Murthy and Rasmussen; the report does not give the term) took the 2D Geyer and Herr reflex model in Simulink, reduced the maximum isometric force of tibialis anterior in one leg to 33% of healthy (265 N of 800 N), and re-optimized 32 controller parameters (16 per leg: reflex gains, offsets and position gains) with CMA-ES on a cost of effort, speed and distance. The simulated stride (1.01 m, 1.64 s, 0.65 m/s) fell within one standard deviation of published drop-foot patient data. The 2D model raised its knee more than patients do, which the authors attribute to the missing out-of-plane compensation.
- **Links.** Course page: <https://sites.google.com/andrew.cmu.edu/ri-lsg/teaching-16-868>. Project page: <https://www.michaeldermksian.com/biomechanics-walker/>. Report: <https://www.michaeldermksian.com/biomechanics-report.pdf>.

### Georgia Tech ME 6409 Biomechatronics of Wearable Robotic Devices

- **Course.** ME 6409, Spring 2026 syllabus, taught by Dr. Aaron Young and Dr. Greg Sawicki.
- **What the course covers.** Human-machine interaction for wearable robots that restore or augment movement, run as two parallel threads: the "human machine" (locomotion neuromechanics and energetics, muscle-tendon actuation, biological sensing and control) and the engineered device (actuators, sensors, low, mid and high-level control, evaluation). Weekly MATLAB/Simulink sessions build a Hill-type muscle-tendon model, with series and parallel elasticity, which "will form the backbone for students to add a wearable robotic device to their model". One of the five case studies is on ankle weakness.
- **The original task.** The final project (40%) is "a computer simulation of your own design set up to address a hypothesis-driven question relevant to wearable robotics", with a mid-semester proposal that lists the independent and dependent variables and the hypotheses, and a report of at most 6 pages in journal format.
- **Links.** Syllabus: <https://syllabus.gatech.edu/sites/default/files/2026-04/Wearable%20Robotics%20Fall%202026%20USG%20Syllabus.pdf>. A separate portfolio project in the same final-project format is [me6409-joint-moment-estimation](https://github.com/mzlumi/me6409-joint-moment-estimation).

### UCLA MAE 263E Bionic Systems Engineering

- **Course.** MAE 263E, taught by Prof. Tyler R. Clites (Anatomical Engineering Group). The syllabus prints no term; its calendar fits Winter 2022.
- **What the course covers.** Design principles for bionic systems, both wearable robots and implantable devices: neural control of movement, neuromusculoskeletal modeling, actuator design, sensor integration, robotic control, neural interfacing, amputation surgery and orthopaedic implants. MATLAB and OpenSim, six problem sets, a midterm and a final project.
- **The original task.** "Simulate a movement pathology and design a wearable robotic system to improve human function."
- **Links.** Syllabus: <https://fec.seas.ucla.edu/wp-content/uploads/fec/Syllabus_MAE263E.pdf>.

### Utah ME EN 7960 Wearable Robotics

- **Course.** ME EN 7960-001, taught by Dr. Tommaso Lenzi. The syllabus prints no year; its calendar fits Fall 2022.
- **What the course covers.** Design, modeling and control of powered exoskeletons and robotic prostheses: morphology, actuation (DC motors, series and parallel elastic, variable stiffness and variable transmission actuators), biosignals, and low, mid and high-level control (finite-state machines, phase-based control), with a project on an open-source robotic leg prosthesis from the Bionic Engineering Lab.
- **The original task.** Homework 1 dimensions an advanced actuator from human biomechanics ("Dimension a series elastic actuator to minimize the energy consumption of a powered ankle prosthesis"). Homework 3 develops and simulates a low-level closed-loop controller for that actuator. The low-level control readings are Vallery et al. (IROS 2007) and Paine et al. (TMECH 2014).
- **Links.** Syllabus: <https://rmcoeh.com/images/pdfs-doc/courses-syllabi/MEEN%207960%20Syllabus.pdf>.

### Stanford BIOE/ME 485 Modeling and Simulation of Human Movement

- **Course.** BIOE/ME 485, taught by Prof. Scott Delp, Spring 2023 offering. The course resources are on the OpenSim documentation site.
- **What the course covers.** OpenSim tutorials (musculoskeletal modeling, tendon transfer, scaling, inverse kinematics and dynamics), four labs and a student research project.
- **The original task.** Lab 1, "Simulation-Based Design to Prevent Ankle Injuries": in a drop landing on a sloped surface, compare no AFO, a soft and a stiff passive AFO, then design an active orthotic by optimizing the timing and level of a torque motor at the ankle, and test muscle co-activation.
- **Links.** Course page: <https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084234/BIOE-ME+485+Spring+2023>. Lab 1: <https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53088618>.

### Notre Dame AME 60553 Wearable Robotics

- **Course.** AME 60553, taught by Prof. Edgar Bolivar-Nieto (Wearable Robotics Laboratory), first offered in 2023.
- **What the course covers.** Compliant actuation for exoskeletons, exosuits and prostheses, dynamic models of the body and the robot, hierarchical control through state variables, finite-state machines and impedance control, optimization for design and real-time control, and evaluation of health outcomes. The lecture notes are linked publicly from the course page.
- **What this project takes from it.** Motor selection (L9), the role of series and parallel elasticity (L12), and impedance, finite-state and phase-variable control of powered orthoses (L21).
- **Links.** Course page and notes: <https://werolab.nd.edu/teaching/wr/>.

### Also related: EPFL BIOENG-404 Analysis and Modelling of Locomotion

The 2021 SCONE assignment of this course (Bruel, Stanev, Di Russo and Ijspeert) optimizes the same `Human0914` model with a Geyer and Herr reflex controller, then simulates heel walking from plantarflexor weakness, toe walking from hyperreflexia, and a self-chosen change that should produce heel or toe walking. That assignment is done in the companion repository [scone-pathological-gait](https://github.com/mzlumi/scone-pathological-gait), which also keeps its handout. It is not repeated here.

All retrieved course documents are listed in [`docs/SOURCES.md`](docs/SOURCES.md).

## The problem

**Model.** SCONE's planar `Human0914` model: 9 degrees of freedom, 7 muscles per leg (hamstrings, gluteus maximus, iliopsoas, vasti, gastrocnemius, soleus, tibialis anterior), foot-ground contact, driven by the Geyer and Herr (2010) reflex controller and optimized with CMA-ES for walking at about 1.2 m/s with low effort.

**Impairment.** Unilateral right-side drop foot: the maximum isometric force of `tib_ant_r` is scaled to 50%, 25% and 10% of healthy. Each level is simulated twice: with the healthy controller unchanged (the immediate effect) and after re-optimizing an asymmetric controller (the model's version of patient compensation). Drop foot is quantified with clinical metrics on the affected side: minimum toe clearance in swing, ankle angle at initial contact, peak swing dorsiflexion, a foot-slap index (peak plantarflexion velocity just after heel strike), steppage (extra hip and knee flexion in swing), left-right asymmetry and cost of transport.

**Device.** A unilateral ankle exoskeleton built from a brushless DC motor, a gearbox of ratio N and a series spring of stiffness k:

1. **Torque requirement.** The torque that the missing tibialis anterior strength would have produced over the gait cycle, plus a 20% margin.
2. **Actuator sizing.** A motor model (torque constant, resistance, reflected inertia) and a sweep over N and k for one real motor, giving electrical energy per stride with the speed, current and voltage limits masked out.
3. **Torque control.** A PID plus feedforward controller on spring-deflection torque, its small-signal bandwidth and its large-signal tracking under saturation, reduced to a first-order-plus-delay model that the simulated device must obey.
4. **Gait events from a shank IMU.** The exoskeleton does not see the simulator's contact forces. It sees one gyroscope on the right shank, sampled at 100 Hz with white noise, a constant bias and a 10 to 20 ms delay. A causal detector finds heel strike and toe-off from the shank angular velocity and estimates gait phase from the running stride time.
5. **Controllers.** A passive AFO (a rotational spring, stiffness swept) and a phase-based active AFO (viscous braking in early stance, zero torque in mid and late stance, PD toward dorsiflexion in swing), both applied as equal and opposite moments on the shank and foot.

**Experiment.** Four conditions (healthy; drop foot with no device; with the passive AFO; with the active AFO). Each device condition is run with the reflex parameters frozen (the first day with the device) and re-optimized with the device on (adaptation), with 3 seeds each. The hypothesis and primary metric are written in this README and committed before the comparison is run. Robustness is tested at a second walking speed, with doubled IMU noise and delay, and with a push or trip.

Example hypothesis from the assignment: at 25% tibialis anterior strength, the active AFO restores minimum toe clearance to within 10 mm of healthy without reducing peak ankle push-off power, while the best passive AFO reduces push-off power by more than 15%.

## Data

[`data/README.md`](data/README.md) describes every input and how to get it. In short:

- **SCONE** (Apache-2.0 core, GPL-3.0 GUI) and its tutorial scenarios and `Human0914` model. `python scripts/fetch_data.py scone` downloads the tutorial files from scone-core at a pinned commit; the application is installed by hand from SimTK.
- **Camargo et al. (2021)** open dataset (22 adults, treadmill and level-ground walking with IMUs on the trunk, thigh, shank and foot, OpenSim kinematics and kinetics; CC BY 4.0, about 1 GB per subject): normative curves for the healthy model and real shank gyroscope signals for testing the event detector. Downloaded by hand in a browser.
- **One motor datasheet**, chosen during actuator sizing.

Nothing is downloaded into git; `data/raw/` is ignored. Optimized `.par` files are committed so every result can be re-run without re-optimizing.

## Going beyond the coursework

- **A realistic sensor in the loop.** No course project triggered its device from a simulated wearable sensor. Here the detector sees a sampled, noisy, biased and delayed gyroscope, and its timing errors are measured against contact-force ground truth on both healthy and drop-foot gait, because the shank pattern changes when the foot drops.
- **Delay sensitivity.** The benefit of the active AFO is measured as a function of detector and actuator delay, giving a curve of how much latency the controller tolerates.
- **Sim-to-real check of the detector.** The same detector, without retuning, is run on real shank gyroscope data from the Camargo et al. dataset and scored against force-plate events.
- **Spread, not single runs.** CMA-ES is random. Every condition is reported as mean and spread over seeds, falls are counted as results, and the adaptation question (frozen versus re-optimized reflexes) is part of the design.
- **Hardware limits in the loop.** The device torque passes through a fitted model of the sized actuator, so the simulated device cannot apply torque instantly or beyond its limits.

## Validation

- **Healthy model.** Stride-averaged hip, knee and ankle angles, ankle moment and vertical ground reaction force against normative data at a matching speed, with RMSE and Pearson r per curve.
- **Drop-foot model.** Compared with the CMU result (a walking gait at 33% tibialis anterior strength) and with the clinical picture of drop foot: does steppage appear, and does foot slap?
- **Device torque bookkeeping.** SCONE external moments persist until removed, so a constant-torque test checks that the device applies exactly the commanded moment pair and nothing accumulates.
- **Event detector.** Heel-strike and toe-off timing error (mean and SD, in ms) and missed and false detection rates over at least 50 strides, on simulated healthy and drop-foot gait and on real data.
- **Actuator and controller.** Unit tests of the motor model (energy balance, the rigid limit as k grows) and of the torque controller (closed-loop gain, bandwidth from the Bode plot), and a check that the fitted low-order model reproduces the full model's step response.
- **Reproducibility.** Each figure is regenerated by one command from committed results.

## Status

- [ ] Package scaffolding, tests and CI; SCONE runner reused from the companion repository
- [ ] Stride segmentation and clinical gait metrics, with tests on synthetic signals
- [ ] Normative curves from the Camargo et al. dataset
- [ ] Part A: healthy baseline over 3 seeds, compared with normative data
- [ ] Part B: drop-foot model at 50%, 25% and 10% strength, immediate and adapted, with metrics
- [ ] Part C: torque requirement, motor model and (N, k) actuator sweep
- [ ] Part D: simulated shank gyroscope and causal event detector, validated on simulated gait
- [ ] Event detector tested on real shank IMU data (sim-to-real)
- [ ] Part E: SEA torque controller, bandwidth, saturation and fitted actuator model
- [ ] Device moment bookkeeping test and passive AFO stiffness sweep
- [ ] Hypothesis and primary metric committed before the experiment
- [ ] Phase-based active AFO controller
- [ ] Part F: experiment over all conditions, both adaptation modes and 3 seeds
- [ ] Robustness tests and the delay-sensitivity curve
- [ ] Figures from one command, side-by-side video of the three drop-foot conditions, report
- [ ] Final README with results and a "what did not work" section

## Credit

The course material in `docs/source/` belongs to the universities and instructors named above: Carnegie Mellon University (Hartmut Geyer), Georgia Tech (Aaron Young and Greg Sawicki), UCLA (Tyler Clites), the University of Utah (Tommaso Lenzi), Stanford University (Scott Delp and the OpenSim team) and the University of Notre Dame (Edgar Bolivar-Nieto). The CMU project report is by Michael Dermksian, Alanna Mitchell, Vybhav Murthy and Eric Rasmussen. These files are kept here for private reference only and must be removed (`docs/source/`) before this repository is made public. The EPFL SCONE handout is by Alice Bruel, Dimitar Stanev, Andrea Di Russo and Auke Ijspeert and is kept only in the companion repository.

SCONE and its tutorial models are by Thomas Geijtenbeek (Apache-2.0 and GPL-3.0). The Camargo et al. dataset is by Jonathan Camargo, Aditya Ramanathan, Will Flanagan and Aaron Young (CC BY 4.0).

This is an independent project, not coursework: Parmida Mazloomi is not enrolled in any of these courses and nothing here was submitted for a grade. The project specification in `docs/assignment.md` adapts the course tasks. The code is written for this project; no code from past students' solutions is used. The plan, the specification and parts of the code and documentation are prepared with the help of an AI assistant and reviewed by Parmida.
