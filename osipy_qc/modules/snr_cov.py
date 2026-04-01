"""
snr_cov.py — SNR, Spatial CoV, and histogram analysis.

sCoV (sigma/mu in GM) is a proxy for transit time heterogeneity.
Published reference: Mutsaerts et al. (2017, JCBFM, 37(9): 3184-3192)
reported mean GM sCoV of 56.9 +/- 13.2% in 186 elderly patients.

Core layer module: works on CBF map + GM mask.

Reference:
    Mutsaerts HJ et al. (2017). "The spatial coefficient of variation
    in ASL cerebral blood flow images." JCBFM, 37(9): 3184-3192.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from osipy_qc.registry import BaseQCCheck, ModuleResult, register_qc_check
from osipy_qc.verdict import Verdict, verdict_from_thresholds


def compute_snr(cbf_map: np.ndarray, gm_mask: np.ndarray) -> float:
    """SNR = mean(GM CBF) / std(GM CBF)."""
    gm_cbf = cbf_map[gm_mask]
    if gm_cbf.size < 2:
        return 0.0
    std = float(np.std(gm_cbf))
    if std < 1e-6:
        return 0.0
    return float(np.mean(gm_cbf) / std)


def compute_spatial_cov(cbf_map: np.ndarray, gm_mask: np.ndarray) -> float:
    """
    Spatial CoV = 100 * std / mean within GM (expressed as %).

    Pitfall: negative CBF values drive mean toward zero which
    makes the ratio explode. So we restrict to strictly positive
    GM voxels (P_GM > 0.5) within the brain mask.
    """
    gm_cbf = cbf_map[gm_mask]
    # Restrict to positive values to avoid mean->0 explosion
    pos = gm_cbf[gm_cbf > 0]
    if pos.size < 2:
        return 0.0
    mean_val = float(np.mean(pos))
    if abs(mean_val) < 1e-6:
        return 0.0
    return 100.0 * float(np.std(pos)) / mean_val


def compute_histogram_metrics(
    cbf_map: np.ndarray,
    gm_mask: np.ndarray,
) -> dict[str, float]:
    """
    Compute histogram-based QC metrics for GM CBF distribution.

    Expected GM CBF in healthy adults: 50-70 mL/100g/min.
    Strongly left-skewed with >10% negative voxels = severe noise.
    """
    gm_cbf = cbf_map[gm_mask]
    if gm_cbf.size == 0:
        return {"mean": 0.0, "median": 0.0, "skewness": 0.0, "neg_frac": 0.0}

    mean_val = float(np.mean(gm_cbf))
    median_val = float(np.median(gm_cbf))
    neg_frac = float((gm_cbf < 0).mean())

    # Skewness (pure numpy, no scipy)
    std = float(np.std(gm_cbf))
    if std > 1e-6:
        skewness = float(np.mean(((gm_cbf - mean_val) / std) ** 3))
    else:
        skewness = 0.0

    return {
        "mean": round(mean_val, 2),
        "median": round(median_val, 2),
        "skewness": round(skewness, 4),
        "neg_frac": round(neg_frac, 4),
    }


@register_qc_check("snr_cov")
class SNRCovCheck(BaseQCCheck):
    """
    SNR, spatial CoV, and histogram analysis — core layer module.

    Works on CBF map + GM probability map (minimal inputs).
    """

    required_inputs = ["cbf_map", "gm_prob"]

    def run(self, data: dict[str, Any], config: dict[str, Any]) -> ModuleResult:
        cbf = data["cbf_map"]
        gm_prob = data["gm_prob"]
        gm_mask = gm_prob > 0.5

        snr = compute_snr(cbf, gm_mask)
        scov = compute_spatial_cov(cbf, gm_mask)
        hist = compute_histogram_metrics(cbf, gm_mask)

        # Determine verdict based on sCoV and negative fraction
        scov_verdict = verdict_from_thresholds(
            scov,
            fail_above=config.get("scov_fail_above", 90.0),
            warn_above=config.get("scov_warn_above", 70.0),
        )
        neg_verdict = verdict_from_thresholds(
            hist["neg_frac"],
            fail_above=config.get("neg_frac_fail_above", 0.20),
            warn_above=config.get("neg_frac_warn_above", 0.10),
        )

        # Take the worse of the two
        if Verdict.FAIL in (scov_verdict, neg_verdict):
            verdict = Verdict.FAIL
        elif Verdict.WARN in (scov_verdict, neg_verdict):
            verdict = Verdict.WARN
        else:
            verdict = Verdict.PASS

        reasons = []
        if scov_verdict != Verdict.PASS:
            reasons.append(f"sCoV={scov:.1f}%")
        if neg_verdict != Verdict.PASS:
            reasons.append(f"neg_frac={hist['neg_frac']:.1%}")

        return ModuleResult(
            name="snr_cov",
            verdict=verdict,
            metrics={
                "snr": round(snr, 4),
                "spatial_cov_pct": round(scov, 2),
                **{f"histogram_{k}": v for k, v in hist.items()},
            },
            reason="; ".join(reasons) if reasons else "",
        )
