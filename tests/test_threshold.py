"""Tests for cohort-level threshold derivation (IQR, GMM, KDE)."""

import numpy as np
import pytest

from osipy_qc.threshold import (
    GMMResult,
    IQRResult,
    KDEResult,
    ThresholdReport,
    compare_methods,
    gmm_valley_threshold,
    iqr_fences,
    kde_valley_threshold,
)

# ──────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def bimodal_scores():
    """Bimodal QEI-like distribution: good cluster ~0.85, poor cluster ~0.35."""
    rng = np.random.default_rng(42)
    good = rng.normal(0.85, 0.05, 40)
    poor = rng.normal(0.35, 0.08, 15)
    return np.concatenate([good, poor])


@pytest.fixture
def unimodal_scores():
    """Unimodal distribution (all good scans)."""
    rng = np.random.default_rng(42)
    return rng.normal(0.90, 0.03, 50)


# ──────────────────────────────────────────────────────────────────────────────
# IQR tests
# ──────────────────────────────────────────────────────────────────────────────

def test_iqr_basic(bimodal_scores):
    """IQR fences should be computed correctly."""
    result = iqr_fences(bimodal_scores)
    assert isinstance(result, IQRResult)
    assert result.q1 < result.q3
    assert result.lower_fence < result.q1
    assert result.upper_fence > result.q3
    assert result.n == len(bimodal_scores)


def test_iqr_rejects_too_few():
    """IQR requires ≥4 values."""
    with pytest.raises(ValueError, match="≥4"):
        iqr_fences(np.array([1.0, 2.0, 3.0]))


def test_iqr_handles_nan():
    """NaN and inf values should be excluded."""
    v = np.array([1.0, 2.0, 3.0, 4.0, 5.0, np.nan, np.inf])
    result = iqr_fences(v)
    assert result.n == 5


# ──────────────────────────────────────────────────────────────────────────────
# GMM tests
# ──────────────────────────────────────────────────────────────────────────────

def test_gmm_finds_bimodal_split(bimodal_scores):
    """GMM should find a threshold between the two modes."""
    result = gmm_valley_threshold(bimodal_scores, higher_is_better=True)
    assert isinstance(result, GMMResult)
    # Threshold should be between the two modes
    assert result.mean_poor < result.threshold < result.mean_good
    assert not result.used_fallback


def test_gmm_higher_vs_lower(bimodal_scores):
    """Direction flag should swap good/poor labels."""
    res_higher = gmm_valley_threshold(bimodal_scores, higher_is_better=True)
    res_lower = gmm_valley_threshold(bimodal_scores, higher_is_better=False)
    # The means should be swapped
    assert res_higher.mean_good > res_higher.mean_poor
    assert res_lower.mean_good < res_lower.mean_poor


def test_gmm_rejects_too_few():
    """GMM requires ≥10 samples."""
    with pytest.raises(ValueError, match="≥10"):
        gmm_valley_threshold(np.array([1.0] * 5))


def test_gmm_deterministic(bimodal_scores):
    """Same seed should give identical results."""
    r1 = gmm_valley_threshold(bimodal_scores, seed=0)
    r2 = gmm_valley_threshold(bimodal_scores, seed=0)
    assert r1.threshold == r2.threshold


# ──────────────────────────────────────────────────────────────────────────────
# KDE tests
# ──────────────────────────────────────────────────────────────────────────────

def test_kde_finds_bimodal_split(bimodal_scores):
    """KDE should find a valley between two peaks."""
    result = kde_valley_threshold(bimodal_scores, higher_is_better=True)
    assert isinstance(result, KDEResult)
    # Threshold should be roughly between the two cluster centers
    assert 0.3 < result.threshold < 0.9
    assert result.bandwidth > 0


def test_kde_unimodal_fallback(unimodal_scores):
    """KDE on unimodal data should return median-like fallback."""
    result = kde_valley_threshold(unimodal_scores)
    assert isinstance(result, KDEResult)
    # Should still return a valid threshold
    assert np.isfinite(result.threshold)


def test_kde_rejects_too_few():
    """KDE requires ≥10 samples."""
    with pytest.raises(ValueError, match="≥10"):
        kde_valley_threshold(np.array([1.0] * 5))


# ──────────────────────────────────────────────────────────────────────────────
# Combined comparison tests
# ──────────────────────────────────────────────────────────────────────────────

def test_compare_methods_returns_report(bimodal_scores):
    """compare_methods should run all three and return ThresholdReport."""
    report = compare_methods(bimodal_scores, "QEI", higher_is_better=True)
    assert isinstance(report, ThresholdReport)
    assert report.metric == "QEI"
    assert report.n == len(bimodal_scores)
    assert report.recommended_method in ("IQR", "GMM", "KDE")
    assert np.isfinite(report.recommended_threshold)


def test_compare_methods_spatial_cov():
    """Lower-is-better metric (spatial CoV) should work correctly."""
    rng = np.random.default_rng(99)
    good = rng.normal(8.0, 2.0, 35)   # low CoV = good
    poor = rng.normal(25.0, 5.0, 15)   # high CoV = bad
    values = np.concatenate([good, poor])

    report = compare_methods(values, "spatial_cov", higher_is_better=False)
    assert report.higher_is_better is False
    assert report.gmm.mean_good < report.gmm.mean_poor
