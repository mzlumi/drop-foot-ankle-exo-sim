from pathlib import Path

from dropfoot.runs import curate, latest_run, par_files, summarize_run


def _run(folder: Path, files: dict[int, float], last: int) -> Path:
    folder.mkdir(parents=True)
    for gen, best in files.items():
        (folder / f"{gen:04d}_{best + 0.01:.3f}_{best:.3f}.par").write_text("p 1 1 0.1\n")
    lines = ["generation\tbest_fitness"] + [f"{g}\t0.5" for g in range(last + 1)]
    (folder / "history.txt").write_text("\n".join(lines) + "\n")
    (folder / "ResultGait10.par").write_text("not a numbered file\n")
    return folder


def test_best_is_last_file_and_convergence(tmp_path):
    run = _run(tmp_path / "261006.0700.R1", {0: 6.1, 5: 0.6, 50: 0.551, 90: 0.549}, last=100)
    assert [g for g, _, _ in par_files(run)] == [0, 5, 50, 90]
    s = summarize_run(run, seed=1, window=40, rel=0.01)
    assert (s.best_generation, s.best_cost, s.generations) == (90, 0.549, 100)
    assert s.best_cost_window_start == 0.551
    assert s.converged


def test_not_converged_when_still_improving(tmp_path):
    run = _run(tmp_path / "r", {0: 2.0, 70: 1.0}, last=100)
    s = summarize_run(run, seed=2, window=40, rel=0.01)
    assert s.best_cost_window_start == 2.0
    assert not s.converged


def test_continuation_skips_the_copied_init_file(tmp_path):
    run = _run(tmp_path / "r", {0: 0.8, 30: 0.6}, last=50)
    (run / "0149_13.066_0.817.par").write_text("p 1 1 0.1\n")
    (run / "config.scone").write_text(
        'CmaOptimizer {\n\tinit_file = "../runs/x.s2/R2/0149_13.066_0.817.par"\n'
        '\tstate_init_file = "InitStateGait10.sto"\n}\n'
    )
    s = summarize_run(run, seed=2, window=40, rel=0.01)
    assert (s.best_generation, s.best_cost) == (30, 0.6)
    assert s.init_file.endswith("0149_13.066_0.817.par")


def test_curate_and_latest(tmp_path):
    _run(tmp_path / "runs" / "261006.0700.R1", {0: 1.0}, last=3)
    newer = _run(tmp_path / "runs" / "261006.0800.R1", {0: 0.9, 2: 0.8}, last=3)
    assert latest_run(tmp_path / "runs") == newer
    curate(newer, 1, tmp_path / "out")
    assert (tmp_path / "out" / "best.par").exists()
    assert (tmp_path / "out" / "run.json").read_text().count('"best_generation": 2')
