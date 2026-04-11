"""Tests for the renal cortex-medulla QC module."""

import numpy as np
import pytest

from osipy_qc.modules.renal_cortex_medulla import (
    RenalCortexMedullaCheck,
    compute_renal_metrics,
)
from osipy_qc.verdict import Verdict

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def kidney_masks():
    """Create synthetic cortex and medulla masks."""
    shape = (20, 20, 10)
    cortex = np.zeros(shape)
    medulla = np.zeros(shape)
    # Cortex = outer shell, medulla = inner core
    cortex[5:15, 5:15, 2:8] = 1.0
    cortex[8:12, 8:12, 3:7] = 0.0   # hollow out center
    medulla[8:12, 8:12, 3:7] = 1.0  # medulla fills center
    return cortex, medulla


def _make_perfusion(cortex_mask, medulla_mask, cortex_cbf, medulla_cbf, rng=None):
    """Build a perfusion map with specified cortex/medulla CBF values."""
    if rng is None:
        rng = np.random.default_rng(42)
    perf = np.zeros_like(cortex_mask, dtype=float)
    perf[cortex_mask > 0.5] = cortex_cbf + rng.normal(0, 5, (cortex_mask > 0.5).sum())
    perf[medulla_mask > 0.5] = medulla_cbf + rng.normal(0, 3, (medulla_mask > 0.5).sum())
    return perf


# ──────────────────────────────────────────────────────────────────────────────
# compute_renal_metrics tests
# ──────────────────────────────────────────────────────────────────────────────

def test_renal_metrics_basic(kidney_masks):
    """Metrics should compute correct means and ratio."""
    cortex, medulla = kidney_masks
    perf = _make_perfusion(cortex, medulla, cortex_cbf=300, medulla_cbf=80)
    m = compute_renal_metrics(perf, cortex, medulla)

    assert 280 < m["mean_cortex_cbf"] < 320
    assert 70 < m["mean_medulla_cbf"] < 90
    assert 3.0 < m["cortex_medulla_ratio"] < 5.0
    assert m["cortex_voxels"] > 0
    assert m["medulla_voxels"] > 0


def test_renal_metrics_zero_medulla(kidney_masks):
    """If medulla is empty, ratio should be 0."""
    cortex, _ = kidney_masks
    empty = np.zeros_like(cortex)
    perf = _make_perfusion(cortex, empty, cortex_cbf=300, medulla_cbf=0)
    m = compute_renal_metrics(perf, cortex, empty)
    assert m["cortex_medulla_ratio"] == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# RenalCortexMedullaCheck verdict tests
# ──────────────────────────────────────────────────────────────────────────────

def test_healthy_kidney_passes(kidney_masks):
    """Healthy cortex/medulla ratio (3:1 to 5:1) should PASS."""
    cortex, medulla = kidney_masks
    perf = _make_perfusion(cortex, medulla, cortex_cbf=300, medulla_cbf=80)

    check = RenalCortexMedullaCheck()
    data = {"perfusion_map": perf, "cortex_mask": cortex, "medulla_mask": medulla}
    result = check.run(data, config={})

    assert result.verdict == Verdict.PASS
    assert "within expected range" in result.reason


def test_borderline_ratio_warns(kidney_masks):
    """Ratio between 2.0 and 3.0 should WARN."""
    cortex, medulla = kidney_masks
    # ratio ~2.5 (borderline)
    perf = _make_perfusion(cortex, medulla, cortex_cbf=200, medulla_cbf=80)

    check = RenalCortexMedullaCheck()
    data = {"perfusion_map": perf, "cortex_mask": cortex, "medulla_mask": medulla}
    result = check.run(data, config={})

    assert result.verdict == Verdict.WARN
    assert "below expected" in result.reason


def test_ckd_like_ratio_fails(kidney_masks):
    """Ratio below 2.0 (CKD-like) should FAIL."""
    cortex, medulla = kidney_masks
    # ratio ~1.25 (severe CKD)
    perf = _make_perfusion(cortex, medulla, cortex_cbf=100, medulla_cbf=80)

    check = RenalCortexMedullaCheck()
    data = {"perfusion_map": perf, "cortex_mask": cortex, "medulla_mask": medulla}
    result = check.run(data, config={})

    assert result.verdict == Verdict.FAIL


def test_low_cortex_cbf_fails(kidney_masks):
    """Very low cortex CBF should FAIL regardless of ratio."""
    cortex, medulla = kidney_masks
    perf = _make_perfusion(cortex, medulla, cortex_cbf=50, medulla_cbf=10)

    check = RenalCortexMedullaCheck()
    data = {"perfusion_map": perf, "cortex_mask": cortex, "medulla_mask": medulla}
    result = check.run(data, config={})

    assert result.verdict == Verdict.FAIL
    assert "labeling failure" in result.reason


def test_low_hematocrit_warns(kidney_masks):
    """Hematocrit < 0.30 should add a warning."""
    cortex, medulla = kidney_masks
    perf = _make_perfusion(cortex, medulla, cortex_cbf=300, medulla_cbf=80)

    check = RenalCortexMedullaCheck()
    data = {
        "perfusion_map": perf,
        "cortex_mask": cortex,
        "medulla_mask": medulla,
        "hematocrit": 0.25,
    }
    result = check.run(data, config={})

    assert result.verdict == Verdict.WARN
    assert "hematocrit" in result.reason.lower()


def test_graceful_degradation_missing_masks():
    """Pipeline should gracefully handle missing renal masks (UNKNOWN)."""
    from osipy_qc.pipeline import run_qc

    rng = np.random.default_rng(42)
    gm = np.zeros((10, 10, 10))
    gm[3:7, 3:7, 3:7] = 0.9
    wm = np.zeros_like(gm)
    wm[4:6, 4:6, 4:6] = 0.8

    data = {
        "cbf_map": 50.0 * gm + 20.0 * wm + rng.normal(0, 2, gm.shape),
        "gm_prob": gm,
        "wm_prob": wm,
    }

    result = run_qc(data)
    # Renal module should be UNKNOWN (missing perfusion_map, cortex_mask, medulla_mask)
    assert result["modules"]["renal_cortex_medulla"]["verdict"] == "UNKNOWN"
    assert "renal_cortex_medulla" in result["modules_skipped"]
