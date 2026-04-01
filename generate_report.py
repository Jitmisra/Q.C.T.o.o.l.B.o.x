#!/usr/bin/env python3
"""
generate_report.py — Generate a premium HTML QC report with rich
                     neuroimaging visualizations embedded as base64 PNGs.

Renders 8 visualization types per subject (4 more than competitor):
  1. CBF Heatmap (axial mid-slice)
  2. Tissue Mask Overlay (GM red / WM blue contours)
  3. CBF Distribution Histogram (GM/WM/CSF)
  4. Control/Label Timecourse
  5. Tri-Plane CBF View (axial + coronal + sagittal)  ← UNIQUE
  6. Frame-wise Displacement Timeseries               ← UNIQUE
  7. Motion Parameters (6-param: 3 translation + 3 rotation) ← UNIQUE
  8. QEI Radar Chart (PSS / DI / Neg Fraction)        ← UNIQUE
"""

from pathlib import Path
import base64
import io

import numpy as np
from scipy.ndimage import gaussian_filter, zoom

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib.gridspec as gridspec

from osipy_qc import run_qc
from osipy_qc.config import QCConfig
from osipy_qc.reporting import generate_html_report


# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────

PLOT_BG = "#1C1B1A"
PLOT_TEXT = "#E5E0DA"
ACCENT = "#C65D3E"


def _fig_to_b64(fig) -> str:
    """Render a matplotlib figure to a base64-encoded PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight",
                facecolor=fig.get_facecolor(), dpi=120)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _style_ax(ax, title=""):
    """Apply consistent dark styling to an axis."""
    ax.set_facecolor(PLOT_BG)
    if title:
        ax.set_title(title, fontsize=9, fontweight="bold",
                     color=PLOT_TEXT, pad=8)
    ax.tick_params(colors="#a4b0be", labelsize=7)
    for spine in ax.spines.values():
        spine.set_color("#333")


# ──────────────────────────────────────────────────────────────
# 1. CBF Heatmap
# ──────────────────────────────────────────────────────────────

def render_cbf_slice(cbf_map, title="") -> str:
    mid = cbf_map[:, :, cbf_map.shape[2] // 2]
    fig, ax = plt.subplots(figsize=(3.2, 3.2), facecolor=PLOT_BG)
    im = ax.imshow(mid.T, origin="lower", cmap="hot",
                   vmin=-10, vmax=100, interpolation="bilinear")
    ax.set_title(title, fontsize=9, fontweight="bold",
                 color=PLOT_TEXT, pad=6)
    ax.axis("off")
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=7, colors=PLOT_TEXT)
    cbar.set_label("mL/100g/min", fontsize=7, color=PLOT_TEXT)
    return _fig_to_b64(fig)


# ──────────────────────────────────────────────────────────────
# 2. Tissue Mask Overlay
# ──────────────────────────────────────────────────────────────

def render_tissue_overlay(cbf_map, gm_prob, wm_prob) -> str:
    mid_cbf = cbf_map[:, :, cbf_map.shape[2] // 2]
    mid_gm = gm_prob[:, :, gm_prob.shape[2] // 2]
    mid_wm = wm_prob[:, :, wm_prob.shape[2] // 2]

    fig, ax = plt.subplots(figsize=(3.2, 3.2), facecolor=PLOT_BG)
    ax.imshow(mid_cbf.T, origin="lower", cmap="hot",
              vmin=-10, vmax=100, interpolation="bilinear")
    if mid_gm.any():
        ax.contour(mid_gm.T, levels=[0.5], colors=["#ff4757"],
                   linewidths=0.8, alpha=0.85)
    if mid_wm.any():
        ax.contour(mid_wm.T, levels=[0.5], colors=["#3742fa"],
                   linewidths=0.8, alpha=0.85)
    from matplotlib.lines import Line2D
    ax.legend(
        [Line2D([0], [0], color="#ff4757", lw=2),
         Line2D([0], [0], color="#3742fa", lw=2)],
        ["GM Boundary", "WM Boundary"],
        loc="upper right", fontsize=7,
        facecolor=PLOT_BG, edgecolor="#333", labelcolor="white",
    )
    ax.set_title("Tissue Mask Overlay", fontsize=9, fontweight="bold",
                 color=PLOT_TEXT, pad=6)
    ax.axis("off")
    return _fig_to_b64(fig)


# ──────────────────────────────────────────────────────────────
# 3. CBF Histogram
# ──────────────────────────────────────────────────────────────

def render_cbf_histogram(cbf_map, gm_prob, wm_prob, csf_prob) -> str:
    fig, ax = plt.subplots(figsize=(3.2, 2.4), facecolor=PLOT_BG)
    _style_ax(ax, "CBF Distribution")

    gm_mask = gm_prob > 0.5
    wm_mask = wm_prob > 0.5
    csf_mask = csf_prob > 0.5

    if gm_mask.any():
        ax.hist(cbf_map[gm_mask], bins=40, color="#ff4757",
                alpha=0.65, label="GM")
    if wm_mask.any():
        ax.hist(cbf_map[wm_mask], bins=40, color="#3742fa",
                alpha=0.65, label="WM")
    if csf_mask.any():
        ax.hist(cbf_map[csf_mask], bins=40, color="#2ed573",
                alpha=0.65, label="CSF")

    ax.set_xlabel("CBF (mL/100g/min)", fontsize=7, color=PLOT_TEXT)
    ax.legend(loc="upper right", fontsize=7,
              facecolor=PLOT_BG, edgecolor="#333", labelcolor="white")
    return _fig_to_b64(fig)


# ──────────────────────────────────────────────────────────────
# 4. Control/Label Timecourse
# ──────────────────────────────────────────────────────────────

def render_timecourse(n_volumes, asl_context, seed=42) -> str:
    rng = np.random.default_rng(seed)
    base = 615 + np.cumsum(rng.normal(0, 0.15, n_volumes))
    signal = np.where(
        [c == "control" for c in asl_context[:n_volumes]],
        base + rng.normal(2.5, 0.3, n_volumes),
        base - rng.normal(1.0, 0.2, n_volumes),
    )

    fig, ax = plt.subplots(figsize=(3.2, 2.4), facecolor=PLOT_BG)
    _style_ax(ax, "Mean Signal Timecourse")

    x = np.arange(n_volumes)
    ax.plot(x, signal, color="#a4b0be", linewidth=1.0, zorder=1)

    c_idx = [i for i, c in enumerate(asl_context[:n_volumes]) if c == "control"]
    l_idx = [i for i, c in enumerate(asl_context[:n_volumes]) if c == "label"]
    if c_idx:
        ax.scatter(c_idx, signal[c_idx], color="#2ed573", s=14, zorder=2, label="Control")
    if l_idx:
        ax.scatter(l_idx, signal[l_idx], color="#ff4757", s=14, zorder=2, label="Label")

    ax.set_xlabel("Volume", fontsize=7, color=PLOT_TEXT)
    ax.legend(loc="upper right", fontsize=7,
              facecolor=PLOT_BG, edgecolor="#333", labelcolor="white")
    return _fig_to_b64(fig)


# ──────────────────────────────────────────────────────────────
# 5. Tri-Plane CBF View (UNIQUE — competitor doesn't have)
# ──────────────────────────────────────────────────────────────

def render_triplane(cbf_map, title="") -> str:
    """Render axial, coronal, and sagittal mid-slices side-by-side."""
    fig, axes = plt.subplots(1, 3, figsize=(7.5, 2.6), facecolor=PLOT_BG)

    slices = [
        (cbf_map[:, :, cbf_map.shape[2] // 2].T, "Axial"),
        (cbf_map[:, cbf_map.shape[1] // 2, :].T, "Coronal"),
        (cbf_map[cbf_map.shape[0] // 2, :, :].T, "Sagittal"),
    ]

    for ax, (sl, label) in zip(axes, slices):
        im = ax.imshow(sl, origin="lower", cmap="hot",
                       vmin=-10, vmax=100, interpolation="bilinear")
        ax.set_title(label, fontsize=8, fontweight="bold",
                     color=PLOT_TEXT, pad=4)
        ax.axis("off")

    cbar = fig.colorbar(im, ax=axes.tolist(), fraction=0.02, pad=0.04)
    cbar.ax.tick_params(labelsize=6, colors=PLOT_TEXT)
    cbar.set_label("mL/100g/min", fontsize=7, color=PLOT_TEXT)

    fig.suptitle(title or "Tri-Plane CBF View", fontsize=10,
                 fontweight="bold", color=PLOT_TEXT, y=1.02)
    return _fig_to_b64(fig)


# ──────────────────────────────────────────────────────────────
# 6. Frame-wise Displacement (UNIQUE — competitor doesn't have)
# ──────────────────────────────────────────────────────────────

def render_fwd_timeseries(motion_params, fwd_threshold=0.5) -> str:
    """Render FWD over time with threshold line and spike markers."""
    # Compute FWD from motion params
    n = motion_params.shape[0]
    fwd = np.zeros(n)
    for i in range(1, n):
        trans_diff = motion_params[i, :3] - motion_params[i - 1, :3]
        rot_diff = motion_params[i, 3:] - motion_params[i - 1, 3:]
        rot_mm = rot_diff * 50  # 50mm sphere radius
        fwd[i] = np.sum(np.abs(trans_diff)) + np.sum(np.abs(rot_mm))

    fig, ax = plt.subplots(figsize=(7.5, 2.2), facecolor=PLOT_BG)
    _style_ax(ax, "Frame-wise Displacement (FWD)")

    x = np.arange(n)
    ax.fill_between(x, fwd, color=ACCENT, alpha=0.3)
    ax.plot(x, fwd, color=ACCENT, linewidth=1.2, zorder=2)

    # Threshold line
    ax.axhline(fwd_threshold, color="#ff4757", linewidth=1.0,
               linestyle="--", alpha=0.8, label=f"Threshold ({fwd_threshold} mm)")

    # Spike markers
    spikes = np.where(fwd > fwd_threshold)[0]
    if len(spikes) > 0:
        ax.scatter(spikes, fwd[spikes], color="#ff4757", s=20,
                   zorder=3, label=f"Spikes ({len(spikes)})")

    ax.set_xlabel("Volume", fontsize=7, color=PLOT_TEXT)
    ax.set_ylabel("FWD (mm)", fontsize=7, color=PLOT_TEXT)
    ax.legend(loc="upper right", fontsize=7,
              facecolor=PLOT_BG, edgecolor="#333", labelcolor="white")
    return _fig_to_b64(fig)


# ──────────────────────────────────────────────────────────────
# 7. Motion Parameters (6-param) (UNIQUE)
# ──────────────────────────────────────────────────────────────

def render_motion_params(motion_params) -> str:
    """Render 6 motion parameters (3 trans + 3 rot) over time."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.5, 3.2),
                                    facecolor=PLOT_BG, sharex=True)
    _style_ax(ax1, "Translation (mm)")
    _style_ax(ax2, "Rotation (rad)")

    x = np.arange(motion_params.shape[0])
    colors_t = ["#ff4757", "#2ed573", "#3742fa"]
    colors_r = ["#ffa502", "#ff6b81", "#70a1ff"]
    labels_t = ["X", "Y", "Z"]
    labels_r = ["Pitch", "Roll", "Yaw"]

    for i in range(3):
        ax1.plot(x, motion_params[:, i], color=colors_t[i],
                 linewidth=1.0, label=labels_t[i], alpha=0.85)
        ax2.plot(x, motion_params[:, i + 3], color=colors_r[i],
                 linewidth=1.0, label=labels_r[i], alpha=0.85)

    ax1.legend(loc="upper right", fontsize=6, ncol=3,
               facecolor=PLOT_BG, edgecolor="#333", labelcolor="white")
    ax2.legend(loc="upper right", fontsize=6, ncol=3,
               facecolor=PLOT_BG, edgecolor="#333", labelcolor="white")
    ax2.set_xlabel("Volume", fontsize=7, color=PLOT_TEXT)
    fig.tight_layout(pad=1.0)
    return _fig_to_b64(fig)


# ──────────────────────────────────────────────────────────────
# 8. QEI Radar Chart (UNIQUE)
# ──────────────────────────────────────────────────────────────

def render_qei_radar(pss, di, neg, qei) -> str:
    """Render a radar/spider chart for QEI components."""
    fig, ax = plt.subplots(figsize=(3.2, 3.2), facecolor=PLOT_BG,
                           subplot_kw=dict(projection='polar'))
    ax.set_facecolor(PLOT_BG)

    categories = ["Structural\nSimilarity", "Spatial\nVariability\n(1-norm)", "Negative\nFraction\n(1-norm)"]
    # Normalize: PSS is already 0-1, DI and neg need inversion (lower is better)
    vals = [pss, max(0, 1 - min(di, 1.0)), max(0, 1 - min(neg, 1.0))]
    vals += vals[:1]  # Close polygon

    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    angles += angles[:1]

    ax.plot(angles, vals, color=ACCENT, linewidth=2, zorder=2)
    ax.fill(angles, vals, color=ACCENT, alpha=0.25, zorder=1)

    # Grid
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=7, color=PLOT_TEXT)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0.25", "0.50", "0.75", "1.00"],
                        fontsize=6, color="#888")
    ax.yaxis.grid(True, color="#333", linewidth=0.5)
    ax.xaxis.grid(True, color="#333", linewidth=0.5)
    ax.spines["polar"].set_color("#333")

    # Center label
    ax.text(0, 0, f"QEI\n{qei:.2f}", ha="center", va="center",
            fontsize=14, fontweight="bold", color=PLOT_TEXT,
            bbox=dict(boxstyle="round,pad=0.3", fc=PLOT_BG,
                      ec=ACCENT, lw=1.5))

    ax.set_title("QEI Component Analysis", fontsize=9, fontweight="bold",
                 color=PLOT_TEXT, pad=20)
    return _fig_to_b64(fig)


# ──────────────────────────────────────────────────────────────
# Subject data generation
# ──────────────────────────────────────────────────────────────

_REAL_DATA_CACHE = None

def get_real_mni_data():
    """Download and cache the real MNI ICBM152 anatomical template masks."""
    global _REAL_DATA_CACHE
    if _REAL_DATA_CACHE is not None:
        return _REAL_DATA_CACHE
    
    try:
        from nilearn.datasets import fetch_icbm152_2009
        import nibabel as nib
        import warnings
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mni = fetch_icbm152_2009()
            
        gm_img = nib.load(mni.gm).get_fdata()
        wm_img = nib.load(mni.wm).get_fdata()
        csf_img = nib.load(mni.csf).get_fdata()
        
        # Downsample real 1mm anatomical masks to typical ASL resolution
        scale = 1/3.0
        gm = np.clip(zoom(gm_img, scale, order=1), 0, 1)
        wm = np.clip(zoom(wm_img, scale, order=1), 0, 1)
        csf = np.clip(zoom(csf_img, scale, order=1), 0, 1)
        
        _REAL_DATA_CACHE = (gm, wm, csf)
        return _REAL_DATA_CACHE
    except Exception as e:
        print(f"Warning: Falling back to synthetic geometries due to: {e}")
        return None

def make_subject(subject_id, quality="good", motion_level="low"):
    """Generate synthetic but highly realistic ASL data from REAL structural MNI templates."""
    rng = np.random.default_rng(hash(subject_id) % 2**31)

    real_data = get_real_mni_data()
    if real_data:
        gm, wm, csf = real_data
        gm, wm, csf = gm.copy(), wm.copy(), csf.copy()
        shape = gm.shape
        brain_mask = ((gm + wm + csf) > 0.05).astype(float)
    else:
        # Fallback synthetic geometry (if internet fails)
        shape = (60, 80, 60)
        X, Y, Z = np.ogrid[:shape[0], :shape[1], :shape[2]]
        cx, cy, cz = 30, 42, 30

        width_modifier = 1.0 + 0.15 * ((Y - cy) / 32.0)
        rx, ry, rz = 21.0 * width_modifier, 34.0, 24.0

        r_sq = ((X - cx)/rx)**2 + ((Y - cy)/ry)**2 + ((Z - cz)/rz)**2
        brain_mask = (r_sq < 1.0).astype(float)

        noise_lf = gaussian_filter(rng.normal(0, 1, shape), sigma=4.0) * 1.5
        noise_hf = gaussian_filter(rng.normal(0, 1, shape), sigma=1.5) * 0.8
        r_perturbed = r_sq + noise_lf + noise_hf

        gm = ((r_perturbed < 1.0) & (r_perturbed > 0.55)).astype(float)
        wm = (r_perturbed <= 0.55).astype(float)

        dist_mid = np.abs(X - cx)
        fissure = (dist_mid < 1.5) & (r_sq < 0.95)
        wm[fissure] = 0.0
        gm[(dist_mid >= 1.5) & (dist_mid < 3.5) & fissure] = 1.0

        lv_x = np.abs(X - cx)
        ventricles = (lv_x > 2.5) & (lv_x < 6.5) & (Y > 30) & (Y < 55) & (np.abs(Z - 30) < 6)
        csf = ventricles.astype(float)
        csf[fissure] = 1.0

        gm[csf > 0] = 0
        wm[csf > 0] = 0

        gm[brain_mask == 0] = 0
        wm[brain_mask == 0] = 0
        csf[brain_mask == 0] = 0

        gm = gaussian_filter(gm, sigma=0.6)
        wm = gaussian_filter(wm, sigma=0.6)
        csf = gaussian_filter(csf, sigma=0.6)

    # 5. Generate typical physiological parameters (CBF & M0)
    # Normal GM CBF ~ 60, Normal WM CBF ~ 22  (mL/100g/min)
    cbf_signal = 60.0 * gm + 22.0 * wm
    m0_signal = 1000.0 * gm + 800.0 * wm + 1200.0 * csf

    noise_scale = {"good": 2.0, "medium": 8.0, "noisy": 20.0, "terrible": 40.0}
    cbf_noise = rng.normal(0, noise_scale.get(quality, 2.0), shape) * brain_mask
    m0_noise = rng.normal(0, 25.0, shape) * brain_mask
    
    cbf = cbf_signal + cbf_noise
    m0_data = m0_signal + m0_noise
    cbf[brain_mask == 0] = 0
    m0_data[brain_mask == 0] = 0

    # 6. Synthesize 6D Motion timeseries
    motion_scale = {"low": 0.005, "medium": 0.05, "high": 0.3}
    motion = rng.normal(0, motion_scale.get(motion_level, 0.005), (60, 6))

    return {
        "cbf_map": cbf,
        "gm_prob": gm,
        "wm_prob": wm,
        "csf_prob": csf,
        "motion_params": motion,
        "asl_context": ["control", "label"] * 30,
        "asl_json": {
            "ArterialSpinLabelingType": "PCASL",
            "PostLabelingDelay": 1.8,
            "LabelingDuration": 1.8,
        },
        "n_volumes": 60,
        "m0_data": m0_data,
        "m0_json": {"RepetitionTime": 6.0},
    }


# ──────────────────────────────────────────────────────────────
# Main execution
# ──────────────────────────────────────────────────────────────

subjects = [
    ("sub-01", "good",     "low"),
    ("sub-02", "good",     "medium"),
    ("sub-03", "medium",   "low"),
    ("sub-04", "noisy",    "high"),
    ("sub-05", "good",     "low"),
    ("sub-06", "terrible", "high"),
    ("sub-07", "good",     "low"),
    ("sub-08", "medium",   "medium"),
]

config = QCConfig.from_yaml("configs/adult_3T.yaml")
results = []

for sid, quality, motion in subjects:
    print(f"  Processing {sid}... (quality={quality}, motion={motion})")
    data = make_subject(sid, quality, motion)
    result = run_qc(data, config=config)
    result["subject_id"] = sid

    # Extract QEI components for radar
    qei_m = result["modules"]["qei"]["metrics"]

    # Render ALL 8 visualizations
    print(f"    Rendering 8 brain visuals for {sid}...")
    result["images"] = {
        # Same 4 as competitor (but better styled)
        "cbf_slice": render_cbf_slice(
            data["cbf_map"],
            f"{sid}  (QEI: {qei_m['qei']:.2f})",
        ),
        "tissue_overlay": render_tissue_overlay(
            data["cbf_map"], data["gm_prob"], data["wm_prob"],
        ),
        "cbf_histogram": render_cbf_histogram(
            data["cbf_map"], data["gm_prob"], data["wm_prob"], data["csf_prob"],
        ),
        "timecourse": render_timecourse(
            60, data["asl_context"],
            seed=hash(sid) % 2**31,
        ),
        # 4 UNIQUE visualizations competitor DOES NOT HAVE
        "triplane": render_triplane(
            data["cbf_map"], f"{sid} — Tri-Plane View",
        ),
        "fwd_timeseries": render_fwd_timeseries(
            data["motion_params"],
        ),
        "motion_params": render_motion_params(
            data["motion_params"],
        ),
        "qei_radar": render_qei_radar(
            pss=qei_m["structural_similarity"],
            di=qei_m["spatial_variability"],
            neg=qei_m["negative_voxel_fraction"],
            qei=qei_m["qei"],
        ),
    }

    results.append(result)

# Generate report
html = generate_html_report(
    results,
    config_name="adult_3T",
    dataset_name="ADNI_Cohort_Demo_2024",
)

out_path = Path("qc_report.html")
out_path.write_text(html)
print(f"\n  Report saved to: {out_path.resolve()}")
print(f"  Open in browser: file://{out_path.resolve()}")
