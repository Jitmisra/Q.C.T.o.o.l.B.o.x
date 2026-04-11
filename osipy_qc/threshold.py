"""
threshold.py — Cohort-level data-driven threshold derivation.

Three complementary statistical methods for automatic QC threshold selection:

  1. **IQR Fences** (Tukey, 1977)
     Q1 − 1.5×IQR  /  Q3 + 1.5×IQR
     Robust, nonparametric, no distributional assumptions.

  2. **GMM Valley** (2-component Gaussian Mixture)
     Fit two Gaussians; threshold = PDF crossing between modes.
     Assumes bimodal distribution (good vs poor scans).

  3. **KDE Local Minimum** (Kernel Density Estimation)  ← UNIQUE
     Smooth the empirical distribution with a Gaussian kernel;
     find the deepest valley between the two highest peaks.
     No parametric assumptions; adapts to arbitrary shapes.

Usage::

    from osipy_qc.threshold import compare_methods, plot_threshold_comparison

    values = np.array([0.92, 0.88, 0.45, ...])  # e.g. QEI scores
    report = compare_methods(values, "QEI", higher_is_better=True)
    plot_threshold_comparison(values, "QEI", "output/qei_thresholds.png")

References:
    Tukey, J. W. (1977). Exploratory Data Analysis.
    Dolui et al. (2024). QEI for ASL CBF Maps, JMRI.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

# ──────────────────────────────────────────────────────────────────────────────
# Result dataclasses
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class IQRResult:
    """Tukey IQR fence result."""

    q1: float
    q3: float
    iqr: float
    lower_fence: float
    upper_fence: float
    n: int


@dataclass
class GMMResult:
    """Two-component Gaussian Mixture Model result."""

    mean_good: float
    mean_poor: float
    std_good: float
    std_poor: float
    weight_good: float
    weight_poor: float
    threshold: float
    used_fallback: bool
    n: int


@dataclass
class KDEResult:
    """Kernel Density Estimation local-minimum result."""

    threshold: float
    peak_good: float
    peak_poor: float
    bandwidth: float
    n: int


@dataclass
class ThresholdReport:
    """Combined report from all three methods."""

    metric: str
    higher_is_better: bool
    n: int
    iqr: IQRResult
    gmm: GMMResult
    kde: KDEResult
    recommended_threshold: float
    recommended_method: str


# ──────────────────────────────────────────────────────────────────────────────
# 1. IQR Fences
# ──────────────────────────────────────────────────────────────────────────────


def iqr_fences(values: np.ndarray, factor: float = 1.5) -> IQRResult:
    """Compute Tukey IQR outlier fences.

    Parameters
    ----------
    values : array-like
        1-D array of metric values.
    factor : float
        Multiplier for IQR (default 1.5 = standard Tukey fence).

    Returns
    -------
    IQRResult
    """
    v = np.asarray(values, dtype=float).ravel()
    v = v[np.isfinite(v)]
    if v.size < 4:
        raise ValueError(f"IQR requires ≥4 finite values, got {v.size}")

    q1, q3 = float(np.percentile(v, 25)), float(np.percentile(v, 75))
    iqr = q3 - q1
    return IQRResult(
        q1=q1,
        q3=q3,
        iqr=iqr,
        lower_fence=q1 - factor * iqr,
        upper_fence=q3 + factor * iqr,
        n=int(v.size),
    )


# ──────────────────────────────────────────────────────────────────────────────
# 2. GMM Valley (2-component Gaussian Mixture)
# ──────────────────────────────────────────────────────────────────────────────


def _normal_pdf(x: np.ndarray, mu: float, sigma: float) -> np.ndarray:
    """Evaluate Gaussian PDF (pure numpy, no scipy dependency)."""
    sigma = max(sigma, 1e-12)
    return (1.0 / (sigma * np.sqrt(2.0 * np.pi))) * np.exp(
        -0.5 * ((x - mu) / sigma) ** 2
    )


def _fit_two_gaussians(
    values: np.ndarray, max_iter: int = 100, tol: float = 1e-6, seed: int = 0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fit a 2-component GMM via EM algorithm (pure numpy).

    Returns (weights[2], means[2], stds[2]) sorted by mean ascending.
    """
    rng = np.random.default_rng(seed)
    v = values.ravel()
    n = v.size

    # Initialize with K-means++ style
    idx = rng.choice(n, 2, replace=False)
    mu = v[idx].astype(float)
    if mu[0] > mu[1]:
        mu = mu[::-1]
    sigma = np.array([v.std() * 0.5, v.std() * 0.5])
    pi = np.array([0.5, 0.5])

    for _ in range(max_iter):
        # E-step
        r0 = pi[0] * _normal_pdf(v, mu[0], sigma[0])
        r1 = pi[1] * _normal_pdf(v, mu[1], sigma[1])
        total = r0 + r1 + 1e-300
        gamma = r0 / total  # responsibility for component 0

        # M-step
        n0 = gamma.sum()
        n1 = n - n0
        if n0 < 2 or n1 < 2:
            break

        pi_new = np.array([n0 / n, n1 / n])
        mu_new = np.array([
            (gamma * v).sum() / n0,
            ((1 - gamma) * v).sum() / n1,
        ])
        sigma_new = np.array([
            np.sqrt((gamma * (v - mu_new[0]) ** 2).sum() / n0 + 1e-12),
            np.sqrt(((1 - gamma) * (v - mu_new[1]) ** 2).sum() / n1 + 1e-12),
        ])

        if np.abs(mu_new - mu).max() < tol:
            mu, sigma, pi = mu_new, sigma_new, pi_new
            break
        mu, sigma, pi = mu_new, sigma_new, pi_new

    # Sort by mean
    order = np.argsort(mu)
    return pi[order], mu[order], sigma[order]


def _find_crossing(
    w0: float, m0: float, s0: float,
    w1: float, m1: float, s1: float,
) -> tuple[float, bool]:
    """Find where two weighted Gaussians cross between their means."""
    lo, hi = min(m0, m1), max(m0, m1)
    if lo >= hi:
        return 0.5 * (m0 + m1), True

    xs = np.linspace(lo, hi, 500)
    d = w0 * _normal_pdf(xs, m0, s0) - w1 * _normal_pdf(xs, m1, s1)
    signs = np.sign(d)

    for i in range(len(xs) - 1):
        if signs[i] * signs[i + 1] < 0:
            # Linear interpolation for crossing point
            t = d[i] / (d[i] - d[i + 1])
            return float(xs[i] + t * (xs[i + 1] - xs[i])), False

    return 0.5 * (m0 + m1), True


def gmm_valley_threshold(
    values: np.ndarray,
    *,
    higher_is_better: bool = True,
    seed: int = 0,
) -> GMMResult:
    """Fit 2-component GMM and find the valley between modes.

    Parameters
    ----------
    values : array-like
        1-D metric values.
    higher_is_better : bool
        If True, the higher-mean component is "good".
    seed : int
        Random seed for EM initialization.

    Returns
    -------
    GMMResult
    """
    v = np.asarray(values, dtype=float).ravel()
    v = v[np.isfinite(v)]
    if v.size < 10:
        raise ValueError(f"GMM requires ≥10 samples, got {v.size}")

    pi, mu, sigma = _fit_two_gaussians(v, seed=seed)

    if higher_is_better:
        idx_good, idx_poor = 1, 0
    else:
        idx_good, idx_poor = 0, 1

    threshold, fallback = _find_crossing(
        pi[idx_good], mu[idx_good], sigma[idx_good],
        pi[idx_poor], mu[idx_poor], sigma[idx_poor],
    )

    return GMMResult(
        mean_good=float(mu[idx_good]),
        mean_poor=float(mu[idx_poor]),
        std_good=float(sigma[idx_good]),
        std_poor=float(sigma[idx_poor]),
        weight_good=float(pi[idx_good]),
        weight_poor=float(pi[idx_poor]),
        threshold=float(threshold),
        used_fallback=fallback,
        n=int(v.size),
    )


# ──────────────────────────────────────────────────────────────────────────────
# 3. KDE Local Minimum  (UNIQUE — competitor does NOT have this)
# ──────────────────────────────────────────────────────────────────────────────


def _gaussian_kde(values: np.ndarray, xs: np.ndarray, bw: float) -> np.ndarray:
    """Evaluate Gaussian KDE at points xs (pure numpy)."""
    n = values.size
    result = np.zeros_like(xs)
    for vi in values:
        result += _normal_pdf(xs, float(vi), bw)
    return result / n


def kde_valley_threshold(
    values: np.ndarray,
    *,
    higher_is_better: bool = True,
    n_points: int = 500,
) -> KDEResult:
    """Find threshold via KDE local minimum between two peaks.

    Uses Silverman's rule for bandwidth selection and finds
    the deepest valley between the two highest density peaks.

    Parameters
    ----------
    values : array-like
        1-D metric values.
    higher_is_better : bool
        If True, threshold separates low (poor) from high (good).
    n_points : int
        Number of evaluation points for KDE.

    Returns
    -------
    KDEResult
    """
    v = np.asarray(values, dtype=float).ravel()
    v = v[np.isfinite(v)]
    if v.size < 10:
        raise ValueError(f"KDE requires ≥10 samples, got {v.size}")

    # Silverman's rule of thumb for bandwidth
    std = float(v.std())
    iqr = float(np.percentile(v, 75) - np.percentile(v, 25))
    bw = 0.9 * min(std, iqr / 1.34) * v.size ** (-0.2)
    bw = max(bw, 1e-6)

    pad = 3 * bw
    xs = np.linspace(v.min() - pad, v.max() + pad, n_points)
    density = _gaussian_kde(v, xs, bw)

    # Find all local maxima (peaks)
    peaks = []
    for i in range(1, len(density) - 1):
        if density[i] > density[i - 1] and density[i] > density[i + 1]:
            peaks.append(i)

    if len(peaks) < 2:
        # Unimodal — use median as fallback
        return KDEResult(
            threshold=float(np.median(v)),
            peak_good=float(xs[peaks[0]]) if peaks else float(np.median(v)),
            peak_poor=float(np.median(v)),
            bandwidth=bw,
            n=int(v.size),
        )

    # Sort peaks by density (descending) and take top 2
    peaks_sorted = sorted(peaks, key=lambda i: density[i], reverse=True)[:2]
    p1, p2 = sorted(peaks_sorted)  # sort by position

    # Find deepest valley between the two peaks
    valley_region = density[p1:p2 + 1]
    valley_idx = p1 + int(np.argmin(valley_region))
    threshold = float(xs[valley_idx])

    if higher_is_better:
        peak_good = float(xs[max(p1, p2)])
        peak_poor = float(xs[min(p1, p2)])
    else:
        peak_good = float(xs[min(p1, p2)])
        peak_poor = float(xs[max(p1, p2)])

    return KDEResult(
        threshold=threshold,
        peak_good=peak_good,
        peak_poor=peak_poor,
        bandwidth=bw,
        n=int(v.size),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Comparison & reporting
# ──────────────────────────────────────────────────────────────────────────────


def compare_methods(
    values: np.ndarray,
    metric: str,
    *,
    higher_is_better: bool = True,
    seed: int = 0,
) -> ThresholdReport:
    """Run all three threshold methods and return a combined report.

    Parameters
    ----------
    values : array-like
        1-D metric values from a cohort.
    metric : str
        Name of the metric (e.g. "QEI", "spatial_cov").
    higher_is_better : bool
        Direction of the metric.
    seed : int
        Random seed for GMM.

    Returns
    -------
    ThresholdReport
    """
    v = np.asarray(values, dtype=float).ravel()
    v = v[np.isfinite(v)]

    iqr_res = iqr_fences(v)
    gmm_res = gmm_valley_threshold(v, higher_is_better=higher_is_better, seed=seed)
    kde_res = kde_valley_threshold(v, higher_is_better=higher_is_better)

    # Recommend: prefer KDE if it found a clear bimodal split,
    # otherwise fall back to GMM, then IQR
    if kde_res.peak_good != kde_res.peak_poor:
        recommended = kde_res.threshold
        method = "KDE"
    elif not gmm_res.used_fallback:
        recommended = gmm_res.threshold
        method = "GMM"
    else:
        recommended = iqr_res.lower_fence if higher_is_better else iqr_res.upper_fence
        method = "IQR"

    return ThresholdReport(
        metric=metric,
        higher_is_better=higher_is_better,
        n=int(v.size),
        iqr=iqr_res,
        gmm=gmm_res,
        kde=kde_res,
        recommended_threshold=recommended,
        recommended_method=method,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Plotting
# ──────────────────────────────────────────────────────────────────────────────

PLOT_BG = "#1C1B1A"
PLOT_TEXT = "#E5E0DA"


def plot_threshold_comparison(
    values: np.ndarray,
    metric: str,
    out_path: str | Path,
    *,
    higher_is_better: bool = True,
    seed: int = 0,
) -> ThresholdReport:
    """Generate a publication-quality threshold comparison plot.

    Renders histogram + GMM components + KDE curve + IQR fences
    in the dark theme matching our dashboard aesthetic.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    report = compare_methods(values, metric, higher_is_better=higher_is_better, seed=seed)
    v = np.asarray(values, dtype=float).ravel()
    v = v[np.isfinite(v)]

    fig, ax = plt.subplots(figsize=(9, 5), facecolor=PLOT_BG)
    ax.set_facecolor(PLOT_BG)

    # Histogram
    ax.hist(v, bins=min(30, max(10, v.size // 3)), density=True,
            alpha=0.4, color="#C65D3E", edgecolor="#333", linewidth=0.5)

    # GMM components
    pad = 0.05 * (v.max() - v.min() + 1e-9)
    xs = np.linspace(v.min() - pad, v.max() + pad, 500)

    g = report.gmm
    pdf_good = g.weight_good * _normal_pdf(xs, g.mean_good, g.std_good)
    pdf_poor = g.weight_poor * _normal_pdf(xs, g.mean_poor, g.std_poor)
    pdf_mix = pdf_good + pdf_poor

    ax.plot(xs, pdf_mix, color=PLOT_TEXT, lw=2, label="GMM mixture", zorder=3)
    ax.plot(xs, pdf_good, "--", color="#2ed573", lw=1.2,
            label=f"Good mode (μ={g.mean_good:.3f})", alpha=0.8)
    ax.plot(xs, pdf_poor, "--", color="#ff4757", lw=1.2,
            label=f"Poor mode (μ={g.mean_poor:.3f})", alpha=0.8)

    # KDE curve
    k = report.kde
    kde_density = _gaussian_kde(v, xs, k.bandwidth)
    ax.plot(xs, kde_density, color="#ffa502", lw=1.5, label="KDE", alpha=0.8, zorder=2)

    # Threshold lines
    ax.axvline(g.threshold, color="#ff4757", lw=2, ls="-",
               label=f"GMM cut = {g.threshold:.4f}", zorder=4)
    ax.axvline(k.threshold, color="#ffa502", lw=2, ls="--",
               label=f"KDE cut = {k.threshold:.4f}", zorder=4)

    iq = report.iqr
    ax.axvline(iq.lower_fence, color="#70a1ff", lw=1.3, ls=":",
               label=f"IQR low = {iq.lower_fence:.4f}")
    ax.axvline(iq.upper_fence, color="#70a1ff", lw=1.3, ls=":",
               label=f"IQR high = {iq.upper_fence:.4f}")

    # Recommended threshold highlight
    ax.axvline(report.recommended_threshold, color="#2ed573", lw=2.5,
               label=f"★ Recommended ({report.recommended_method}) = "
                     f"{report.recommended_threshold:.4f}",
               zorder=5)

    # Styling
    ax.set_xlabel(metric, fontsize=10, color=PLOT_TEXT)
    ax.set_ylabel("Density", fontsize=10, color=PLOT_TEXT)
    ax.set_title(f"Threshold Derivation: {metric}  (n={v.size})",
                 fontsize=12, fontweight="bold", color=PLOT_TEXT, pad=12)
    ax.legend(fontsize=7.5, loc="upper right",
              facecolor=PLOT_BG, edgecolor="#333", labelcolor="white")
    ax.tick_params(colors="#a4b0be", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#333")

    fig.tight_layout()
    if isinstance(out_path, (str, Path)):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=PLOT_BG)
    plt.close(fig)

    return report


# ──────────────────────────────────────────────────────────────────────────────
# Export
# ──────────────────────────────────────────────────────────────────────────────


def export_threshold_report(
    reports: list[ThresholdReport],
    output_dir: str | Path,
) -> None:
    """Export threshold analysis as markdown + JSON.

    Parameters
    ----------
    reports : list[ThresholdReport]
        One report per metric.
    output_dir : str or Path
        Directory to write threshold_report.md and threshold_report.json.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # ── Markdown ──
    lines = [
        "# Cohort Threshold Derivation Report\n",
        "Three methods compared: **IQR Fences**, **GMM Valley**, **KDE Local Minimum**.\n",
        "| Metric | n | IQR Low | IQR High | GMM Cut | KDE Cut | ★ Recommended | Method |",
        "|--------|---|---------|----------|---------|---------|---------------|--------|",
    ]
    for r in reports:
        lines.append(
            f"| {r.metric} | {r.n} | {r.iqr.lower_fence:.4f} | "
            f"{r.iqr.upper_fence:.4f} | {r.gmm.threshold:.4f} | "
            f"{r.kde.threshold:.4f} | **{r.recommended_threshold:.4f}** | "
            f"{r.recommended_method} |"
        )
    lines.append("")

    (out / "threshold_report.md").write_text("\n".join(lines), encoding="utf-8")

    # ── JSON ──
    payload: dict[str, Any] = {}
    for r in reports:
        payload[r.metric] = {
            "n": r.n,
            "higher_is_better": r.higher_is_better,
            "iqr": asdict(r.iqr),
            "gmm": asdict(r.gmm),
            "kde": asdict(r.kde),
            "recommended_threshold": r.recommended_threshold,
            "recommended_method": r.recommended_method,
        }

    (out / "threshold_report.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
