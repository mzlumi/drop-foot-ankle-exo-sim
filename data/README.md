# Data, models and software

This project is a simulation. Its "data" are the SCONE software and model files that the simulations start from, one public gait dataset used for normative comparison and for a sim-to-real test, and a motor datasheet chosen during actuator sizing. Nothing is downloaded into the repository: [`scripts/fetch_data.py`](../scripts/fetch_data.py) puts files under `data/raw/`, which is git-ignored. Simulation results that the project produces itself (optimized `.par` files, small exported `.sto` files) are committed under `results/`, as the assignment asks.

All pages below were opened on 2025-12-07 to confirm what they contain.

## Overview

| Resource | What the project uses it for | License or terms | Size | Scripted download |
|---|---|---|---|---|
| SCONE application | Running and optimizing the reflex walking model | Apache-2.0 (scone-core), GPL-3.0 (scone-studio GUI) | 23 to 49 MB installer | No: browser download from SimTK |
| SCONE tutorial scenarios and models (`Human0914`) | Starting scenarios, controller, measures, initial states and optimized parameters | Apache-2.0 (in scone-core) | under 0.5 MB | Yes |
| Camargo et al. (2021) dataset | Normative level-walking kinematics and kinetics; real shank IMU signals for the sim-to-real test of the event detector | CC BY 4.0 | about 1 GB per subject, 22 subjects | No: browser download (Dropbox or Mendeley Data) |
| Motor datasheet | Motor constants for the actuator sizing | Manufacturer's terms | one PDF | No: chosen by hand |

## 1. SCONE

SCONE is free, open-source software for predictive simulation of human and animal movement (Geijtenbeek 2019). It optimizes the parameters of a controller, here the Geyer and Herr (2010) reflex controller, with CMA-ES so that a musculoskeletal model achieves a high-level goal such as walking at a target speed with low effort.

- Home page: <https://scone.software>
- Install instructions: <https://scone.software/doku.php?id=install>
- Downloads (SimTK): <https://simtk.org/frs/?group_id=1180>. Version 2.4.5 was released on 2026-10-05 for Windows (23 MB), Linux (`.deb`, 26 MB) and macOS (`.dmg`, 49 MB).
- Source: <https://github.com/tgeijten/scone-core> (Apache-2.0) and <https://github.com/tgeijten/scone-studio> (GPL-3.0).
- Citation: T. Geijtenbeek, "SCONE: Open Source Software for Predictive Simulation of Biological Motion," *Journal of Open Source Software* 4(38), 1421, 2019. <https://doi.org/10.21105/joss.01421>
- The SCONE documentation wiki is CC BY-NC-SA 4.0.

**How to get it.** Download the installer for your system from the SimTK page in a browser. The SimTK download links go through a confirmation page that did not return the file to a scripted request, so `fetch_data.py` does not try. On macOS, the install page explains how to open the app if Gatekeeper blocks it. To run optimizations headless on Linux or in Docker, reuse the runner in the companion repository [mzlumi/scone-pathological-gait](https://github.com/mzlumi/scone-pathological-gait) (`docker/`, `scripts/scone.sh`) rather than writing a second one.

Record the SCONE version used for every result. CMA-ES results change slightly between versions and platforms.

## 2. SCONE tutorial scenarios and the Human0914 model

The assignment starts from SCONE's bundled tutorials. The same files are in scone-core under `scenarios/Tutorials/`. `fetch_data.py` downloads the ones this project needs, pinned to scone-core commit `8cc814822c58356e110027d80962ebf0f024e116` (2026-10-05), into `data/raw/scone-tutorials/`, keeping the folder layout so the `data/...` paths inside the scenarios still resolve.

| File | Use |
|---|---|
| `Tutorial 4a - Gait.scone` | Healthy gait scenario: `Human0914`, `ControllerGH2010.scone`, `MeasureGait10.scone` |
| `Tutorial 4b - Gait at Different Speeds.scone` | Speed variants for the robustness tests |
| `Tutorial 4c - Perturbed Gait.scone` | Template for the push or trip perturbation |
| `Tutorial 5a - Pathological Gait - Weak Plantarflexors.scone` | Shows how to scale `max_isometric_force` per muscle in a `Properties` block |
| `Tutorial 5c - Pathological Gait - Hyper-reflexia.scone` | Optional spasticity extension |
| `Tutorial 6b - Script - Balance Device.scone` | Shows a Lua `ScriptController` that applies an external moment |
| `data/Human0914.osim` | Planar OpenSim 3 model, 7 Millard muscles per leg: `hamstrings`, `glut_max`, `iliopsoas`, `vasti`, `gastroc`, `soleus`, `tib_ant` (suffix `_r` or `_l`) |
| `data/ControllerGH2010.scone`, `data/ControllerGH2010asym.scone` | Symmetric and asymmetric reflex controllers |
| `data/MeasureGait05.scone`, `MeasureGait10.scone`, `MeasureGait15.scone` | Gait measures with different minimum speeds |
| `data/InitStateGait10.sto`, `InitStateGait15.sto` | Initial states |
| `data/ResultGait10.par`, `ResultGait15.par` | Optimized parameters to start from |
| `data/ScriptControllerBalanceDevice.lua` | Lua device example (`add_external_moment`, `ang_pos`, `model:time`) |

Two things checked in these files:

- **External moments persist.** `ScriptControllerBalanceDevice.lua` switches its device off by adding the opposite moment, which confirms the hint in the assignment: a script must track what it has applied and add only the change.
- **One difference from the assignment text.** The assignment says Tutorial 4a uses `MeasureGait05.scone`. In scone-core at the pinned commit, Tutorial 4a uses `MeasureGait10.scone`, and `MeasureGait05.scone` is used by Tutorial 5a and Tutorial 6b. Use the files as they are and state which measure each scenario uses.

The installed SCONE app also ships the tutorials. If its copy differs from the pinned one, use the one that matches the SCONE version you run, and note it.

## 3. Camargo et al. (2021) lower-limb biomechanics dataset

**What it is.** 22 able-bodied adults walking on a treadmill (28 speeds from 0.5 to 1.85 m/s in 0.05 m/s steps), on level ground (slow, normal and fast circuits), on ramps (six inclinations from 5.2 to 18 degrees) and on stairs (four step heights), with transitions. Recorded signals: motion capture markers, force plates, EMG (11 muscles including tibialis anterior, soleus and medial gastrocnemius), goniometers (ankle, knee, hip) and IMUs on the trunk, thigh, shank and foot. OpenSim inverse kinematics and inverse dynamics are included.

- Project page: <https://www.epic.gatech.edu/opensource-biomechanics-camargo-et-al/>
- Dropbox mirror (public view): <https://www.dropbox.com/sh/lhurwcy0znonh56/AAAPmVdrxh7M6FW-UYHyPHyza?dl=0>
- Mendeley Data, three parts: <https://doi.org/10.17632/fcgm3chfff.2>, <https://doi.org/10.17632/k9kvm5tn3f.2>, <https://doi.org/10.17632/jj3r5f9pnf.2> (version 2 of each)
- Usage tutorial by the first author: <https://blog.jcamargo.co/jbiomechanics_dataset/>
- License: **CC BY 4.0** (from the DataCite records of all three Mendeley DOIs). Redistribution is allowed with attribution, but this repository still does not commit the raw files, because of their size.
- Citation: J. Camargo, A. Ramanathan, W. Flanagan and A. Young, "A comprehensive, open-source dataset of lower limb biomechanics in multiple conditions of stairs, ramps, and level-ground ambulation and transitions," *Journal of Biomechanics* 119, 110320, 2021. <https://doi.org/10.1016/j.jbiomech.2021.110320>
- Size: the project page says about 1 GB per subject and recommends downloading subjects one at a time.

**Checked: are raw shank IMU signals included?** Yes. The project page states that the IMUs on the trunk, thigh, shank and foot record 3-axis acceleration and gyroscope data, and the author's tutorial reads an `imu` table with channels such as `thigh_Gyro_Z`. There is no magnetometer. The exact shank channel name (expected `shank_Gyro_Z`) and its sign convention must be confirmed on the first downloaded subject and written here.

**What the project needs.**

- `SubjectInfo.mat` (subject mass and height, used to normalize moments).
- For three to five subjects: the level-ground and treadmill trials, with the `ik`, `id`, `imu` and gait-cycle or force-plate data. Treadmill trials near 1.2 m/s give the normative curves for Part A; the shank gyroscope in the same trials is the real data for the sim-to-real test of the event detector.
- The authors' MATLAB scripts (`STRIDES.m`, `PLOTS.m`, EpicToolbox) are useful as a reference for how strides are split, but the analysis here is written in Python.

The Dropbox listing is rendered with JavaScript, so the folder and file names could not be listed from a script; confirm them on the first download and write them here. The authors' tutorial works in MATLAB (`SubjectInfo.mat`, EpicToolbox for data tables), so expect `.mat` files. If they hold MATLAB table objects, `scipy.io.loadmat` may not read them; check this on the first subject. If they do not load, export the needed tables to CSV once in MATLAB (or Octave), keep the export script in `scripts/`, and keep the CSVs in `data/raw/`.

**How to download.** A browser is needed. The project page describes the Dropbox mirror as a public-view directory, so no account should be required (not tested with a full download). Open the Dropbox link, download `SubjectInfo.mat` and one subject folder at a time (for example `AB06`), and unzip into `data/raw/camargo/` so that you get `data/raw/camargo/SubjectInfo.mat` and `data/raw/camargo/AB06/...`. Running `python scripts/fetch_data.py camargo` prints these steps and then lists what it finds in that folder.

## 4. Normative gait curves

The assignment suggests two references for the healthy-model comparison in Part A:

- **Camargo et al. (2021)**, above: open data, so the normative mean and standard deviation can be computed in code from the downloaded subjects at a matching speed. This is the preferred reference.
- **Winter, *Biomechanics and Motor Control of Human Movement*, 4th ed. (Wiley, 2009)**: a copyrighted book. Its tables may be used for comparison, but must not be copied into the repository.

The companion repository already reads SCONE Studio's built-in normative bands (`gait_analysis_default.zml` from scone-studio, GPL-3.0). If those bands are used here too, depend on that code instead of copying it.

## 5. Motor datasheet

Part C needs one real brushless DC motor (torque constant, winding resistance, rotor inertia, rated current, maximum speed). Pick one from a manufacturer's public datasheet. Write the model number, the datasheet URL and the date you opened it in `actuator/MOTOR.md`, and copy the numbers you use into a small parameter file with a comment pointing to the datasheet page. Do not commit the datasheet PDF itself.

## 6. Private data: never in this repository

Extension 3 of the assignment runs the event detector on shank IMU recordings from Parmida's own motion-lab sessions (her B.Sc. thesis data, collected with Dr. Farahmand's group at Sharif). These recordings are not public. Keep them outside the repository, point to them with an environment variable (for example `THESIS_IMU_DIR`), and commit only aggregate numbers, and only with her supervisor's agreement.
