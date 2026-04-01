"""
qei.py — Quality Evaluation Index (Dolui et al., 2024, JMRI).

Full 3-component implementation using pure numpy (scipy is banned
in osipy to maintain GPU compatibility via the xp = get_array_module()
pattern).

Components:
    1. Structural Similarity (PSS) — Pearson r(CBF, PSCBF)
    2. Spatial Variability (DI) — pooled within-tissue variance / |mean GM CBF|
    3. Negative Voxel Fraction (nGM) — % of GM voxels with CBF < 0

Final QEI = cubic_root(f1 * f2 * f3) where each f_i is a nonlinear
mapping that penalizes bad values toward zero.

Reference:
    Dolui S. et al. (2024). "Automated Quality Evaluation Index for
    ASL-Derived CBF Maps." JMRI, 60(6): 2497-2508.
    DOI: 10.1002/jmri.29308
"""

from __future__ import annotations

from typing import Any

import numpy as np

from osipy_qc.registry import BaseQCCheck, ModuleResult, register_qc_check
from osipy_qc.verdict import Verdict, verdict_from_thresholds


def _pearson_r(x: np.ndarray, y: np.ndarray) -> float:
    """
    Pure-numpy Pearson correlation (no scipy dependency).

    osipy bans scipy to preserve GPU portability via
    xp = get_array_module(). This is a drop-in replacement.
    """
    xm = x - x.mean()
    ym = y - y.mean()
    denom = np.linalg.norm(xm) * np.linalg.norm(ym)
    if denom == 0:
        return 0.0
    return float(np.dot(xm, ym) / denom)


def structural_similarity(
    cbf_map: np.ndarray,
    gm_prob: np.ndarray,
    wm_prob: np.ndarray,
    mask: np.ndarray,
) -> float:
    """
    Compute structural similarity (PSS).

    Builds a pseudo-structural CBF map: PSCBF = 50*GM + 20*WM
    (reflecting healthy GM ~50 mL/100g/min, WM ~20 mL/100g/min).
    Returns Pearson r between actual CBF and PSCBF within mask.

    NOTE: Pragati's implementation uses 2.5*GM + 1.0*WM (ASLPrep
    internal ratio). We use 50*GM + 20*WM per the Dolui 2024 paper
    (actual CBF units). The Pearson r is scale-invariant so the
    value is identical, but using CBF units makes the PSCBF
    interpretable and matches the paper's description.
    """
    pscbf = 50.0 * gm_prob + 20.0 * wm_prob

    valid = mask & np.isfinite(cbf_map) & np.isfinite(pscbf)
    if valid.sum() < 10:
        return 0.0

    r = _pearson_r(cbf_map[valid], pscbf[valid])
    return max(r, 0.0)  # clamp negative to 0


def spatial_variability(
    cbf_map: np.ndarray,
    gm_mask: np.ndarray,
    wm_mask: np.ndarray,
    csf_mask: np.ndarray,
) -> float:
    """
    Compute index of dispersion (DI).

    DI = pooled_variance / |mean_GM_CBF|

    Uses K=3 tissue classes (GM, WM, CSF). Pooled variance:
        V = sum((n_k - 1) * var_k) / sum(n_k - 1)

    High DI = extreme CBF values scattered across tissues
    (motion or transit-time artifacts).
    """
    masks = [gm_mask, wm_mask, csf_mask]
    num = 0.0
    denom = 0.0

    for m in masks:
        n = int(m.sum())
        if n <= 1:
            continue
        vals = cbf_map[m]
        num += (n - 1) * float(np.var(vals))
        denom += (n - 1)

    if denom == 0:
        return 0.0

    pooled_var = num / denom
    mean_gm = float(np.mean(cbf_map[gm_mask])) if gm_mask.any() else 1.0

    if abs(mean_gm) < 1e-6:
        return 0.0

    return max(pooled_var / abs(mean_gm), 0.0)


def negative_voxel_fraction(
    cbf_map: np.ndarray,
    gm_mask: np.ndarray,
) -> float:
    """Fraction of GM voxels with negative CBF (should be ~0 in healthy scans)."""
    gm_cbf = cbf_map[gm_mask]
    if gm_cbf.size == 0:
        return 0.0
    return float((gm_cbf < 0).mean())


def compute_qei(
    pss: float,
    di: float,
    neg_frac: float,
    alpha_pss: float = 3.0126,
    beta_pss: float = 2.4419,
    alpha_di: float = 0.054,
    beta_di: float = 0.9272,
    alpha_neg: float = 2.8478,
    beta_neg: float = 0.5196,
) -> float:
    """
    Combine three components into final QEI score via nonlinear
    mapping + geometric mean.

    f1(r) = 1 - exp(-alpha * r^beta)    — penalizes low correlation
    f2(D) = exp(-alpha * D^beta)         — penalizes high variability
    f3(x) = exp(-alpha * x^beta)         — penalizes negative voxels

    QEI = (f1 * f2 * f3)^(1/3)

    Parameters alpha/beta are from ASLPrep's empirical fit to the
    Dolui 2024 validation cohort. They are configurable (not hardcoded)
    and documented as provisional.
    """
    # Clamp inputs to avoid math errors
    pss = max(pss, 0.0)
    di = max(di, 0.0)
    neg_frac = max(neg_frac, 0.0)

    f1 = 1.0 - np.exp(-alpha_pss * pss ** beta_pss)
    f2 = np.exp(-(alpha_di * di ** beta_di))
    f3 = np.exp(-(alpha_neg * neg_frac ** beta_neg))

    product = f1 * f2 * f3
    if product <= 0:
        return 0.0

    return float(product ** (1.0 / 3.0))


@register_qc_check("qei")
class QEICheck(BaseQCCheck):
    """
    Quality Evaluation Index — anchor metric for CBF map quality.

    Core layer module: works on CBF map + tissue probability maps.
    Always available when these minimal inputs exist.
    """

    required_inputs = ["cbf_map", "gm_prob", "wm_prob"]

    def run(self, data: dict[str, Any], config: dict[str, Any]) -> ModuleResult:
        cbf = data["cbf_map"]
        gm_prob = data["gm_prob"]
        wm_prob = data["wm_prob"]
        csf_prob = data.get("csf_prob", np.zeros_like(gm_prob))

        # Build masks from probability maps (threshold at 0.5)
        gm_mask = gm_prob > 0.5
        wm_mask = wm_prob > 0.5
        csf_mask = csf_prob > 0.5
        brain_mask = gm_mask | wm_mask | csf_mask

        # Handle NaN/Inf before computation
        cbf_clean = np.where(np.isfinite(cbf), cbf, 0.0)

        # Compute three components
        pss = structural_similarity(cbf_clean, gm_prob, wm_prob, brain_mask)
        di = spatial_variability(cbf_clean, gm_mask, wm_mask, csf_mask)
        neg = negative_voxel_fraction(cbf_clean, gm_mask)

        # Final QEI
        qei_score = compute_qei(pss, di, neg)

        # Determine verdict from config thresholds
        v = verdict_from_thresholds(
            qei_score,
            fail_below=config.get("fail_below", 0.30),
            warn_below=config.get("warn_below", 0.55),
        )

        reason = ""
        if v == Verdict.FAIL:
            reason = f"QEI {qei_score:.3f} below FAIL threshold"
        elif v == Verdict.WARN:
            reason = f"QEI {qei_score:.3f} below WARN threshold"

        return ModuleResult(
            name="qei",
            verdict=v,
            metrics={
                "qei": round(qei_score, 4),
                "structural_similarity": round(pss, 4),
                "spatial_variability": round(di, 4),
                "negative_voxel_fraction": round(neg, 4),
            },
            reason=reason,
        )
