import shutil
from pathlib import Path

from dropfoot import evaluation

DATA = Path(__file__).parent / "data"


def test_cache_is_reused_only_while_the_inputs_are_unchanged(tmp_path, monkeypatch):
    calls = []

    def fake_evaluate(scenario, par, out, overrides=None):
        calls.append(Path(par).read_text())
        shutil.copyfile(DATA / "device_pulse.sto", f"{out}.sto")
        Path(f"{out}.txt").write_text("report\n")

    monkeypatch.setattr(evaluation, "EVAL_CACHE", tmp_path)
    monkeypatch.setattr(evaluation.scone, "evaluate", fake_evaluate)
    scen, par = tmp_path / "s.scone", tmp_path / "in.par"
    scen.write_text("scenario\n")
    par.write_text("p 1 1 0.1\n")
    evaluation.evaluate_cached(scen, par, "r")
    evaluation.evaluate_cached(scen, par, "r")
    assert len(calls) == 1
    par.write_text("p 2 1 0.1\n")
    evaluation.evaluate_cached(scen, par, "r")
    evaluation.evaluate_cached(scen, par, "r", {"a": 1})
    assert len(calls) == 3
    (tmp_path / "r.par.key").unlink()
    evaluation.evaluate_cached(scen, par, "r", {"a": 1})
    assert len(calls) == 4
