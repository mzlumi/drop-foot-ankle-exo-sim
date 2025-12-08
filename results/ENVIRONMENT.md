# Environment

Every result in `results/` was produced with the software below. CMA-ES results change slightly between SCONE versions and platforms, so rerun on the same setup before comparing numbers.

## Simulation

| Item | Value |
|---|---|
| SCONE | 2.4.5-RC-2 (`sconecmd`, printed at start-up) |
| Simulation engine | OpenSim 3.3 (`OpenSim-3.3-2021-01-28`), the engine built into SCONE |
| SCONE build | Linux amd64 `.deb` from the scone-studio CI, SHA-256 `368ad591473762d83c0c3d5dae296a303e40ab2a9b798d324dd6e94b192ef6f5` |
| Container | `scone-headless:latest`, image ID `sha256:5fb6c8496db1...`, built from `docker/Dockerfile` of the companion repository [mzlumi/scone-pathological-gait](https://github.com/mzlumi/scone-pathological-gait) at commit `2d137a2` |
| Tutorial files | scone-core commit `8cc814822c58356e110027d80962ebf0f024e116` (fetched by `scripts/fetch_data.py scone`) |
| Model | `Human0914.osim` (planar, 9 degrees of freedom, 7 muscles per leg) |
| Control step | SCONE default, 1 ms (`fixed_control_step_size = 0.001`). A 5 ms step made the tutorial solution fall at 1.4 s and was not faster |
| Data output | 200 Hz, with per-muscle joint moments and powers (`scenarios/settings/scone-settings.zml`, mounted as SCONE's settings file) |
| Runner | `python scripts/run_scone.py` (`src/dropfoot/scone.py`), the same `docker run` call as the companion's `scripts/scone.sh` with this repository mounted at `/work` |

## Host

| Item | Value |
|---|---|
| Computer | Apple M5, 10 cores (4 performance, 6 efficiency), 16 GB RAM |
| Operating system | macOS 27.0.1 (build 26A434) |
| Container runtime | OrbStack 2.2.3, Docker 29.4.0, Linux VM with 10 CPUs and 8 GB RAM |
| Emulation | amd64 image on an arm64 host (Rosetta inside OrbStack) |

## Python

| Package | Version |
|---|---|
| Python | 3.12.13 |
| NumPy | 2.5.3 |
| SciPy | 1.18.1 |
| pandas | 3.0.6 |
| Matplotlib | 3.11.2 |
| pytest | 9.1.1 |
| scone-gait | 0.1.0, companion repository commit `2d137a245daa4520f7525ed84d9c79cd93163749` |
