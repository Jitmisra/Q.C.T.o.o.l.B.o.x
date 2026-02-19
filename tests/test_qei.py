"""Tests for QEI module on synthetic data (no binary blobs in repo)."""

import numpy as np
from osipy_qc.modules.qei import (
    structural_similarity,
    spatial_variability,
    negative_voxel_fraction,
    compute_qei,
    QEICheck,
)
from osipy_qc.verdict import Verdict


def _make_synthetic_brain(shape=(20, 20, 20)):
    """Create synthetic brain with realistic GM/WM/CSF contrast."""
    gm_prob = np.zeros(shape)
    wm_prob = np.zeros(shape)
    csf_prob = np.zeros(shape)

    # GM: cortical shell
    gm_prob[4:16, 4:16, 4:16] = 0.9
    gm_prob[7:13, 7:13, 7:13] = 0.0   # hollow out for WM

    # WM: white matter core
    wm_prob[7:13, 7:13, 7:13] = 0.85

    # CSF: ventricle center
    csf_prob[9:11, 9:11, 9:11] = 0.7

    return gm_prob, wm_prob, csf_prob


def test_structural_similarity_good_scan():
    """Good scan (anatomy-consistent CBF) should have high PSS."""
    gm, wm, csf = _make_synthetic_brain()
    pscbf = 50.0 * gm + 20.0 * wm

    # Good CBF: closely follows anatomy + small noise
    rng = np.random.default_rng(42)
    good_cbf = pscbf + rng.normal(0, 3, pscbf.shape)
    mask = (gm + wm + csf) > 0.1

    r = structural_similarity(good_cbf, gm, wm, mask)
    assert r > 0.90, f"Good scan PSS should be >0.90, got {r:.3f}"


def test_structural_similarity_bad_scan():
    """Random noise scan should have low PSS."""
    gm, wm, csf = _make_synthetic_brain()
    mask = (gm + wm + csf) > 0.1

    rng = np.random.default_rng(42)
    bad_cbf = rng.normal(30, 25, gm.shape)

    r = structural_similarity(bad_cbf, gm, wm, mask)
    assert r < 0.30, f"Bad scan PSS should be <0.30, got {r:.3f}"


def test_spatial_variability_low_for_clean():
    """Clean scan should have relatively low DI."""
    gm, wm, csf = _make_synthetic_brain()
    pscbf = 50.0 * gm + 20.0 * wm + 5.0 * csf
    rng = np.random.default_rng(42)
    clean_cbf = pscbf + rng.normal(0, 2, pscbf.shape)

    gm_mask = gm > 0.5
    wm_mask = wm > 0.5
    csf_mask = csf > 0.5

    di = spatial_variability(clean_cbf, gm_mask, wm_mask, csf_mask)
    assert di < 5.0, f"Clean scan DI should be <5, got {di:.2f}"


def test_negative_voxel_fraction():
    """All-positive GM should have zero negative fraction."""
    gm, wm, csf = _make_synthetic_brain()
    good_cbf = 50.0 * gm + 20.0 * wm
    gm_mask = gm > 0.5

    neg = negative_voxel_fraction(good_cbf, gm_mask)
    assert neg == 0.0


def test_negative_voxel_fraction_noisy():
    """Noisy scan should have substantial negative fraction."""
    gm, wm, csf = _make_synthetic_brain()
    rng = np.random.default_rng(42)
    noisy_cbf = rng.normal(0, 50, gm.shape)  # centered at 0 = lots of negatives
    gm_mask = gm > 0.5

    neg = negative_voxel_fraction(noisy_cbf, gm_mask)
    assert neg > 0.30, f"Noisy scan neg fraction should be >30%, got {neg:.1%}"


def test_compute_qei_perfect():
    """Perfect inputs should yield QEI close to 1."""
    qei = compute_qei(pss=0.98, di=0.1, neg_frac=0.0)
    assert qei > 0.85, f"Perfect QEI should be >0.85, got {qei:.3f}"


def test_compute_qei_terrible():
    """Terrible scan should yield QEI close to 0."""
    qei = compute_qei(pss=0.05, di=10.0, neg_frac=0.40)
    assert qei < 0.20, f"Terrible QEI should be <0.20, got {qei:.3f}"


def test_qei_geometric_mean_collapses():
    """One catastrophic component should collapse entire score."""
    # Good PSS, good DI, but catastrophic negative voxels
    qei = compute_qei(pss=0.95, di=0.5, neg_frac=0.50)
    assert qei < 0.50, f"One bad component should drag QEI down, got {qei:.3f}"


def test_qei_check_full_pipeline():
    """End-to-end QEICheck module on synthetic data."""
    gm, wm, csf = _make_synthetic_brain()
    pscbf = 50.0 * gm + 20.0 * wm

    rng = np.random.default_rng(42)
    good_cbf = pscbf + rng.normal(0, 3, pscbf.shape)

    data = {
        "cbf_map": good_cbf,
        "gm_prob": gm,
        "wm_prob": wm,
        "csf_prob": csf,
    }
    config = {"fail_below": 0.30, "warn_below": 0.55}

    check = QEICheck()
    result = check.run(data, config)

    assert result.name == "qei"
    assert result.verdict == Verdict.PASS
    assert result.metrics["qei"] > 0.55
    assert "structural_similarity" in result.metrics
    assert "spatial_variability" in result.metrics
    assert "negative_voxel_fraction" in result.metrics
