import numpy as np
import pytest

from dropfoot.validation import phase_error, score, true_phase, Run


def test_score_counts_missed_false_and_window():
    true = np.array([1.0, 2.0, 3.0, 4.0, 9.0])
    est = np.array([1.05, 2.4, 3.02, 3.5, 0.98])  # 2.0 missed (0.4 s late), 3.5 is false
    det = est + 0.1
    s = score(true, est, det, t0=0.5, t1=5.0)
    assert s.n_true == 4  # 9.0 is outside the window
    assert s.missed == 2  # 2.0 and 4.0 (3.5 is 0.5 s early)
    np.testing.assert_allclose(np.sort(s.errors), [-0.02, 0.02])  # nearest wins: 0.98 for 1.0
    # 1.05, 2.4 and 3.5 are unpaired and inside the window
    assert s.false == 3
    assert s.summary("hs")["hs_latency_mean_ms"] == pytest.approx(100.0)


def test_detection_of_event_outside_window_is_not_false():
    true = np.array([1.0, 5.1])
    est = np.array([1.02, 4.95])  # 4.95 is inside the window but belongs to 5.1
    s = score(true, est, est, t0=0.5, t1=5.0)
    assert (s.n_true, s.missed, s.false) == (1, 0, 0)


def test_true_phase_and_wrapped_error():
    hs = np.array([1.0, 2.0, 3.2])
    t = np.array([0.5, 1.0, 1.5, 2.6, 3.2])
    np.testing.assert_allclose(true_phase(t, hs), [np.nan, 0.0, 0.5, 0.5, np.nan], equal_nan=True)
    run = Run(t, np.array([-1.0, 0.98, 0.5, 0.45, 0.0]), *(np.array([]),) * 4)
    np.testing.assert_allclose(phase_error(run, hs, 0.0, 5.0), [-0.02, 0.0, -0.05], atol=1e-12)
