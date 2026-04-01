"""Tests for verdict engine and graceful degradation."""

import numpy as np

from osipy_qc.pipeline import run_qc
from osipy_qc.verdict import Verdict, combine_verdicts, verdict_from_thresholds

# --- Verdict combination tests ---

def test_any_fail_condemns_scan():
    """Conservative: any single FAIL -> overall FAIL."""
    assert combine_verdicts([Verdict.PASS, Verdict.FAIL, Verdict.PASS]) == Verdict.FAIL


def test_warn_without_fail():
    """WARN without FAIL -> overall WARN."""
    assert combine_verdicts([Verdict.PASS, Verdict.WARN, Verdict.PASS]) == Verdict.WARN


def test_all_pass():
    """All PASS -> overall PASS."""
    assert combine_verdicts([Verdict.PASS, Verdict.PASS]) == Verdict.PASS


def test_unknown_ignored_in_combination():
    """UNKNOWN modules don't block the overall verdict."""
    assert combine_verdicts([Verdict.PASS, Verdict.UNKNOWN, Verdict.PASS]) == Verdict.PASS


def test_all_unknown():
    """If only UNKNOWN modules, overall is UNKNOWN."""
    assert combine_verdicts([Verdict.UNKNOWN, Verdict.UNKNOWN]) == Verdict.UNKNOWN


# --- Threshold-based verdict tests ---

def test_fail_below():
    assert verdict_from_thresholds(0.2, fail_below=0.3) == Verdict.FAIL


def test_warn_below():
    assert verdict_from_thresholds(0.4, warn_below=0.55) == Verdict.WARN


def test_pass_above_all():
    assert verdict_from_thresholds(0.8, fail_below=0.3, warn_below=0.55) == Verdict.PASS


def test_fail_above():
    assert verdict_from_thresholds(2.0, fail_above=1.5) == Verdict.FAIL


# --- Graceful degradation tests ---

def test_graceful_degradation_missing_inputs():
    """
    When required inputs are missing, modules return UNKNOWN
    instead of crashing. This is the key design difference from
    existing tools.
    """
    # Only provide CBF + GM/WM (enough for QEI + snr_cov)
    # but NOT motion_params, asl_context, m0_data
    gm = np.zeros((10, 10, 10))
    gm[3:7, 3:7, 3:7] = 0.9
    wm = np.zeros((10, 10, 10))
    wm[4:6, 4:6, 4:6] = 0.8

    data = {
        "cbf_map": 50.0 * gm + 20.0 * wm + np.random.default_rng(42).normal(0, 3, gm.shape),
        "gm_prob": gm,
        "wm_prob": wm,
    }

    result = run_qc(data)

    # Pipeline should NOT crash
    assert "overall_verdict" in result

    # QEI and snr_cov should run (they only need cbf + gm/wm)
    assert result["modules"]["qei"]["verdict"] in ("PASS", "WARN", "FAIL")
    assert result["modules"]["snr_cov"]["verdict"] in ("PASS", "WARN", "FAIL")

    # Motion, control_label, m0 should be UNKNOWN (missing inputs)
    assert result["modules"]["motion"]["verdict"] == "UNKNOWN"
    assert result["modules"]["control_label"]["verdict"] == "UNKNOWN"
    assert result["modules"]["m0_check"]["verdict"] == "UNKNOWN"

    # Skipped modules should be listed
    assert "motion" in result["modules_skipped"]
    assert "control_label" in result["modules_skipped"]
    assert "m0_check" in result["modules_skipped"]


def test_full_pipeline_all_inputs():
    """When all inputs provided, all modules should run."""
    gm = np.zeros((10, 10, 10))
    gm[3:7, 3:7, 3:7] = 0.9
    wm = np.zeros((10, 10, 10))
    wm[4:6, 4:6, 4:6] = 0.8
    rng = np.random.default_rng(42)

    data = {
        "cbf_map": 50.0 * gm + 20.0 * wm + rng.normal(0, 2, gm.shape),
        "gm_prob": gm,
        "wm_prob": wm,
        "csf_prob": np.zeros_like(gm),
        "motion_params": rng.normal(0, 0.01, (60, 6)),  # small motion
        "asl_context": ["control", "label"] * 30,
        "asl_json": {
            "ArterialSpinLabelingType": "PCASL",
            "PostLabelingDelay": 1.8,
            "LabelingDuration": 1.8,
        },
        "n_volumes": 60,
        "m0_data": rng.normal(1000, 50, gm.shape),
        "m0_json": {"RepetitionTime": 6.0},
    }

    result = run_qc(data)

    # No modules should be UNKNOWN (except stubs)
    stub_modules = {"renal_cortex_medulla"}  # stub: not yet implemented
    for name, mod in result["modules"].items():
        if name in stub_modules:
            continue
        assert mod["verdict"] != "UNKNOWN", f"{name} should not be UNKNOWN"
