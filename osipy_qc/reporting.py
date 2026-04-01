"""
reporting.py — Standalone HTML report generator for QC results.

Generates a premium, self-contained HTML report (no external dependencies)
matching the QC-ToolBox V1.0 Figma mockups. Features:

1. Batch Overview: aggregate stats, participant ledger, artifact breakdown
2. Per-Subject Deep Dive: QEI breakdown, module checklist, metrics
3. Single Page App (SPA) feel with vanilla JavaScript to switch views
4. Accurate Figma color palette (Light theme with rust/terracotta accents)
5. Zero external JavaScript dependencies
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any


def _load_icon_b64() -> str:
    """Load icon.png from the project root and return as base64 string."""
    # Look for icon.png relative to this file's parent (osipy_qc/) -> project root
    icon_path = Path(__file__).resolve().parent.parent / "icon.png"
    if icon_path.exists():
        return base64.b64encode(icon_path.read_bytes()).decode()
    return ""

# ──────────────────────────────────────────────────────────────
# Color palette (derived exactly from Figma mockups)
# ──────────────────────────────────────────────────────────────

COLORS = {
    "bg": "#FAF8F5",
    "card": "#FFFFFF",
    "sidebar": "#F4F0EB",
    "primary": "#AC4D2A",         # Rust / Terracotta accent
    "primary_light": "#C46B4B",
    "text_main": "#1C1B1A",
    "text_muted": "#6E6864",
    "border": "#E5E0DA",
    "pass": "#2A8A73",            # Teal
    "pass_bg": "#E0F2EF",
    "warn": "#D98026",            # Orange
    "warn_bg": "#FDF2E6",
    "fail": "#A43122",            # Red
    "fail_bg": "#FBDFDB",
    "unknown": "#889299",
    "unknown_bg": "#EAECEE",
    "bar_bg": "#EAE6E1",
}

VERDICT_STYLE = {
    "PASS": {"color": COLORS["pass"], "bg": COLORS["pass_bg"], "label": "PASS"},
    "WARN": {"color": COLORS["warn"], "bg": COLORS["warn_bg"], "label": "WARN"},
    "FAIL": {"color": COLORS["fail"], "bg": COLORS["fail_bg"], "label": "FAIL"},
    "UNKNOWN": {"color": COLORS["unknown"], "bg": COLORS["unknown_bg"], "label": "UNKNOWN"},
}


def _css() -> str:
    return f"""
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    body {{
        font-family: 'Inter', -apple-system, sans-serif;
        background: {COLORS["bg"]};
        color: {COLORS["text_main"]};
        line-height: 1.5;
        overflow-x: hidden;
    }}

    .layout {{
        display: flex;
        min-height: 100vh;
    }}

    /* Sidebar */
    .sidebar {{
        width: 260px;
        background: {COLORS["sidebar"]};
        padding: 32px 24px;
        display: flex;
        flex-direction: column;
        border-right: 1px solid {COLORS["border"]};
        position: fixed;
        height: 100vh;
        overflow-y: auto;
    }}
    .logo-container {{
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 40px;
    }}
    .logo-icon {{
        width: 38px;
        height: 38px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }}
    .logo-icon img {{
        width: 100%;
        height: 100%;
        object-fit: contain;
    }}
    .logo-text-title {{
        font-size: 16px;
        font-weight: 700;
        line-height: 1.2;
    }}
    .logo-text-sub {{
        font-size: 10px;
        color: {COLORS["text_muted"]};
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 2px;
    }}

    .sidebar-nav {{
        display: flex;
        flex-direction: column;
        gap: 8px;
    }}
    .nav-item {{
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 16px;
        border-radius: 8px;
        color: {COLORS["text_muted"]};
        text-decoration: none;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
    }}
    .nav-item:hover {{
        background: rgba(0,0,0,0.03);
        color: {COLORS["text_main"]};
    }}
    .nav-item.active {{
        background: #FFFFFF;
        color: {COLORS["primary"]};
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }}

    /* Main Content */
    .main-content {{
        margin-left: 260px;
        flex: 1;
        display: flex;
        flex-direction: column;
    }}

    /* Topbar */
    .topbar {{
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 16px;
        padding: 20px 48px;
        border-bottom: 1px solid {COLORS["border"]};
    }}
    .topbar-left {{
        display: flex;
        align-items: center;
        gap: 16px;
        flex-shrink: 0;
    }}
    .topbar-title {{
        font-size: 18px;
        font-weight: 700;
        color: {COLORS["primary"]};
        white-space: nowrap;
    }}
    .topbar-links {{
        display: flex;
        gap: 24px;
        font-size: 14px;
        font-weight: 500;
        color: {COLORS["text_muted"]};
        margin-left: auto;
    }}
    .topbar-link {{
        cursor: pointer;
        transition: color 0.2s;
        white-space: nowrap;
    }}
    .topbar-link:hover {{
        color: {COLORS["primary"]};
    }}
    .topbar-link.active {{
        color: {COLORS["primary"]};
        border-bottom: 2px solid {COLORS["primary"]};
        padding-bottom: 4px;
    }}

    .page-container {{
        padding: 0 48px 48px;
        max-width: 1300px;
    }}

    /* Headers */
    .page-header {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 32px;
        margin-top: 24px;
    }}
    .page-title {{
        font-size: 32px;
        font-weight: 700;
        margin-bottom: 8px;
    }}
    .page-subtitle {{
        font-size: 14px;
        color: {COLORS["text_muted"]};
    }}

    .btn {{
        padding: 10px 16px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        border: none;
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }}
    .btn-primary {{
        background: {COLORS["primary"]};
        color: white;
    }}
    .btn-outline {{
        background: white;
        border: 1px solid {COLORS["border"]};
        color: {COLORS["text_main"]};
    }}

    /* Stat Cards (Screen 1) */
    .stats-grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 24px;
        margin-bottom: 32px;
    }}
    .stat-card {{
        background: {COLORS["card"]};
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.02);
    }}
    .stat-tag {{
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        float: right;
    }}
    .stat-title {{
        font-size: 13px;
        color: {COLORS["text_muted"]};
        margin-bottom: 12px;
        font-weight: 500;
    }}
    .stat-value {{
        font-size: 48px;
        font-weight: 800;
        line-height: 1;
        margin-bottom: 16px;
    }}
    .stat-value span {{
        font-size: 24px;
        color: {COLORS["text_muted"]};
        font-weight: 600;
    }}
    .progress-track {{
        height: 6px;
        background: {COLORS["bar_bg"]};
        border-radius: 3px;
        overflow: hidden;
    }}
    .progress-fill {{
        height: 100%;
        border-radius: 3px;
    }}

    /* Cards */
    .card {{
        background: {COLORS["card"]};
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.02);
        margin-bottom: 24px;
    }}
    .card-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }}
    .card-title {{
        font-size: 16px;
        font-weight: 600;
    }}

    /* Layouts */
    .grid-23 {{
        display: grid;
        grid-template-columns: 2fr 1fr;
        gap: 24px;
    }}
    .grid-half {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 24px;
    }}

    /* Table */
    .table {{
        width: 100%;
        border-collapse: collapse;
    }}
    .table th {{
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        color: {COLORS["text_muted"]};
        text-align: left;
        padding: 12px 16px;
        border-bottom: 1px solid {COLORS["border"]};
    }}
    .table td {{
        padding: 16px;
        font-size: 14px;
        border-bottom: 1px solid {COLORS["border"]};
    }}
    .table tr:last-child td {{
        border-bottom: none;
    }}

    .badge {{
        display: inline-flex;
        align-items: center;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
    }}
    .action-link {{
        color: {COLORS["text_muted"]};
        cursor: pointer;
        transition: color 0.2s;
        text-decoration: none;
    }}
    .action-link:hover {{ color: {COLORS["primary"]}; }}

    /* Artifact breakdown bars */
    .artifact-row {{ margin-bottom: 16px; }}
    .artifact-meta {{ display: flex; justify-content: space-between; font-size: 13px; font-weight: 500; margin-bottom: 8px; }}

    /* Screen 2 - Deep Dive Specifics */
    .subject-header-pill {{
        background: {COLORS["pass_bg"]};
        color: {COLORS["pass"]};
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }}
    .subject-huge-title {{
        font-size: 48px;
        font-weight: 800;
        line-height: 1.1;
        margin-top: 16px;
        margin-bottom: 16px;
        max-width: 600px;
    }}
    .subject-desc {{
        font-size: 15px;
        color: {COLORS["text_muted"]};
        max-width: 500px;
        line-height: 1.6;
    }}
    .global-score-container {{
        text-align: right;
    }}
    .global-score-val {{
        font-size: 84px;
        font-weight: 800;
        color: {COLORS["primary"]};
        line-height: 1;
        letter-spacing: -2px;
    }}
    .global-score-label {{
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 1px;
        color: {COLORS["text_muted"]};
        text-transform: uppercase;
        margin-top: 8px;
    }}

    .qei-breakdown-row {{
        display: flex;
        align-items: center;
        margin-bottom: 16px;
    }}
    .qei-breakdown-label {{ font-size: 14px; font-weight: 500; width: 160px; }}
    .qei-breakdown-val {{ font-size: 15px; font-weight: 600; margin-left: auto; }}

    .checklist-item {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 0;
        border-bottom: 1px solid {COLORS["border"]};
    }}
    .checklist-item:last-child {{ border-bottom: none; }}

    /* ── Responsive breakpoints ── */
    @media (max-width: 1200px) {{
        .sidebar {{ width: 220px; padding: 24px 16px; }}
        .main-content {{ margin-left: 220px; }}
        .topbar {{ padding: 20px 32px; }}
        .page-container {{ padding: 0 32px 32px; }}
        .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}

    @media (max-width: 960px) {{
        .sidebar {{ display: none; }}
        .main-content {{ margin-left: 0; }}
        .topbar {{ padding: 16px 24px; }}
        .page-container {{ padding: 0 24px 24px; }}
        .grid-23 {{ grid-template-columns: 1fr; }}
        .page-title {{ font-size: 24px; }}
        .page-header {{ flex-direction: column; gap: 16px; }}
    }}

    @media (max-width: 640px) {{
        .topbar {{
            flex-direction: column;
            align-items: flex-start;
            gap: 12px;
            padding: 16px;
        }}
        .topbar-links {{ margin-left: 0; }}
        .stats-grid {{ grid-template-columns: 1fr; }}
        .page-container {{ padding: 0 16px 16px; }}
        .page-title {{ font-size: 20px; }}
        .table th, .table td {{ padding: 10px 12px; font-size: 12px; }}
    }}
    """

def _js() -> str:
    return """
    function showOverview() {
        document.getElementById('view-overview').style.display = 'block';
        document.getElementById('view-detail').style.display = 'none';
        document.getElementById('nav-overview').classList.add('active');
        document.getElementById('nav-detail').classList.remove('active');
        // Clear sidebar participant highlights
        document.querySelectorAll('.nav-participant').forEach(el => el.classList.remove('active'));
    }

    function showDetail(subjectId) {
        // Hide all detail cards
        const details = document.querySelectorAll('.subject-detail-container');
        details.forEach(el => el.style.display = 'none');

        // Show selected
        const target = document.getElementById('detail-' + subjectId);
        if (target) {
            target.style.display = 'block';
            document.getElementById('view-overview').style.display = 'none';
            document.getElementById('view-detail').style.display = 'block';

            // Update active states
            document.getElementById('nav-overview').classList.remove('active');
            document.getElementById('nav-detail').classList.add('active');

            // Highlight sidebar participant
            document.querySelectorAll('.nav-participant').forEach(el => el.classList.remove('active'));
            var navEl = document.getElementById('nav-p-' + subjectId);
            if (navEl) navEl.classList.add('active');

            document.getElementById('topbar-subject-id').textContent = 'Subject: ' + subjectId;
        }
        window.scrollTo(0,0);
    }

    function exportReport() {
        window.print();
    }

    function newAnalysis() {
        var modal = document.getElementById('analysis-modal');
        modal.style.display = modal.style.display === 'flex' ? 'none' : 'flex';
    }
    """

def _badge(verdict: str) -> str:
    s = VERDICT_STYLE.get(verdict, VERDICT_STYLE["UNKNOWN"])
    return f'<span class="badge" style="background:{s["bg"]}; color:{s["color"]}">{s["label"]}</span>'

def _progress(val: float, max_val: float, color: str, width: str = "100%", height: str = "6px") -> str:
    pct = min(100, (val / max_val) * 100) if max_val > 0 else 0
    return f"""
    <div class="progress-track" style="width:{width}; height:{height};">
        <div class="progress-fill" style="width:{pct}%; background:{color}"></div>
    </div>
    """

def generate_html_report(results: list[dict[str, Any]], config_name: str = "default", dataset_name: str = "Dataset") -> str:
    n_total = len(results)
    verdicts = [r.get("overall_verdict", "UNKNOWN") for r in results]
    n_pass = verdicts.count("PASS")
    n_warn = verdicts.count("WARN")
    n_fail = verdicts.count("FAIL")
    pass_rate = (n_pass / n_total * 100) if n_total else 0
    warn_rate = (n_warn / n_total * 100) if n_total else 0
    fail_rate = (n_fail / n_total * 100) if n_total else 0

    # Primary artifacts counting
    artifact_counts: dict[str, int] = {}
    for r in results:
        for mname, mod in r.get("modules", {}).items():
            if mod.get("verdict") in ("WARN", "FAIL"):
                n = "Motion" if mname == "motion" else "sCoV" if mname == "snr_cov" else mname
                artifact_counts[n] = artifact_counts.get(n, 0) + 1

    # Ledger rows
    ledger_rows = ""
    for r in results:
        sid = r.get("subject_id", "unknown")
        v = r.get("overall_verdict", "UNKNOWN")
        qei_val = r.get("modules", {}).get("qei", {}).get("metrics", {}).get("qei", 0)

        primary_artifact = "None"
        for mname, mod in r.get("modules", {}).items():
            if mod.get("verdict") in ["WARN", "FAIL"]:
                primary_artifact = mname.replace("_", " ").title()
                break

        qei_color = COLORS["pass"] if qei_val >= 0.55 else COLORS["warn"] if qei_val >= 0.3 else COLORS["fail"]

        ledger_rows += f"""
        <tr>
            <td style="font-weight:500">{sid}</td>
            <td>{_badge(v)}</td>
            <td>
                <div style="display:flex;align-items:center;gap:12px">
                    <span style="font-weight:600;min-width:30px">{qei_val:.2f}</span>
                    <div style="flex:1">{_progress(qei_val, 1.0, qei_color, height="4px")}</div>
                </div>
            </td>
            <td><span style="font-size:13px;color:{COLORS['text_muted']}">{primary_artifact}</span></td>
            <td><button class="btn btn-primary" onclick="showDetail('{sid}')" style="padding: 6px 12px; font-size: 12px; border-radius: 6px;">View Report &rarr;</button></td>
        </tr>
        """

    # Artifact bars for Dashboard
    artifact_html = ""
    for name, cnt in sorted(artifact_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
        color = COLORS["primary_light"] if name == "Motion" else COLORS["text_muted"] if name == "m0_check" else "#D4A373"
        artifact_html += f"""
        <div class="artifact-row">
            <div class="artifact-meta">
                <span>{name}</span>
                <span>{cnt}/{n_total}</span>
            </div>
            {_progress(cnt, n_total, color, height="8px")}
        </div>
        """
    if not artifact_html:
        artifact_html = "<div style='color:#889299;font-size:13px;padding:20px 0;'>No artifacts detected.</div>"

    # Sidebar participant list
    sidebar_participants = ""
    for r in results:
        sid = r.get("subject_id", "unknown")
        v = r.get("overall_verdict", "UNKNOWN")
        vs = VERDICT_STYLE.get(v, VERDICT_STYLE["UNKNOWN"])
        sidebar_participants += f"""
        <a class="nav-item nav-participant" id="nav-p-{sid}" onclick="showDetail('{sid}')" style="padding:8px 16px; font-size:13px">
            <span style="width:8px;height:8px;border-radius:50%;background:{vs['color']};display:inline-block;flex-shrink:0"></span>
            {sid}
        </a>
        """

    # Deep Dives
    deep_dives = ""
    for r in results:
        sid = r.get("subject_id", "unknown")
        v = r.get("overall_verdict", "UNKNOWN")
        mods = r.get("modules", {})

        qei_m = mods.get("qei", {}).get("metrics", {})
        qei_val = qei_m.get("qei", 0)
        pss = qei_m.get("structural_similarity", 0)
        di = qei_m.get("spatial_variability", 0)
        neg = qei_m.get("negative_voxel_fraction", 0)

        # Checklist
        checklist = ""
        for mname, mod in mods.items():
            mv = mod.get("verdict", "UNKNOWN")
            m_label = "Quality Index" if mname=="qei" else "Frame Displacement" if mname=="motion" else mname.replace('_', ' ').title()
            checklist += f"""
            <div class="checklist-item">
                <div>
                    <div style="font-weight:600;font-size:14px">{m_label}</div>
                    <div style="font-size:12px;color:{COLORS['text_muted']}">{mod.get('reason', 'Verification passed')[:40]}</div>
                </div>
                {_badge(mv)}
            </div>
            """

        # Fetch real metrics — show N/A when module returned UNKNOWN
        motion_v = mods.get("motion", {}).get("verdict", "UNKNOWN")
        motion_m = mods.get("motion", {}).get("metrics", {})
        mean_fwd = motion_m.get("mean_fwd_mm", 0.0)
        max_fwd = motion_m.get("max_fwd_mm", 0.0)

        snr_v = mods.get("snr_cov", {}).get("verdict", "UNKNOWN")
        snr_m = mods.get("snr_cov", {}).get("metrics", {})
        snr_val = snr_m.get("snr", 0.0)
        scov_val = snr_m.get("spatial_cov_pct", 0.0)
        hist_neg = snr_m.get("histogram_neg_frac", 0.0)

        m0_v = mods.get("m0_check", {}).get("verdict", "UNKNOWN")
        m0_m = mods.get("m0_check", {}).get("metrics", {})
        tr_sec = m0_m.get("tr_seconds", 0.0)
        sat_pct = m0_m.get("saturation_pct", 0.0)

        cl_v = mods.get("control_label", {}).get("verdict", "UNKNOWN")
        cl_reason = mods.get("control_label", {}).get("reason", "")

        na_style = f'font-size:13px;color:{COLORS["unknown"]};font-style:italic'

        # Build motion card content
        if motion_v != "UNKNOWN":
            motion_card = f'''
                <div class="qei-breakdown-row">
                    <div class="qei-breakdown-label">Mean FWD</div>
                    <div class="qei-breakdown-val">{mean_fwd:.3f} mm</div>
                </div>
                <div class="qei-breakdown-row">
                    <div class="qei-breakdown-label">Max FWD</div>
                    <div class="qei-breakdown-val">{max_fwd:.3f} mm</div>
                </div>
                <div style="font-size:12px;color:{COLORS['text_muted']};margin-top:16px">
                    Frame-wise Displacement per Power et al. (2012).
                </div>
            '''
        else:
            motion_card = f'<div style="{na_style};padding:16px 0">N/A — motion parameters not provided.<br>Module gracefully degraded to UNKNOWN.</div>'

        # Build SNR card content
        if snr_v != "UNKNOWN":
            snr_card = f'''
                <div class="qei-breakdown-row">
                    <div class="qei-breakdown-label">Signal-to-Noise Ratio</div>
                    <div class="qei-breakdown-val">{snr_val:.2f}</div>
                </div>
                <div class="qei-breakdown-row">
                    <div class="qei-breakdown-label">Spatial CoV</div>
                    <div class="qei-breakdown-val">{scov_val:.1f}%</div>
                </div>
                <div class="qei-breakdown-row">
                    <div class="qei-breakdown-label">Negative Fraction</div>
                    <div class="qei-breakdown-val">{hist_neg*100:.1f}%</div>
                </div>
            '''
        else:
            snr_card = f'<div style="{na_style};padding:16px 0">N/A — CBF map or tissue maps not provided.</div>'

        # Build M0 card content
        if m0_v != "UNKNOWN":
            m0_card = f'''
                <div class="qei-breakdown-row">
                    <div class="qei-breakdown-label">Repetition Time (TR)</div>
                    <div class="qei-breakdown-val">{tr_sec:.2f} s</div>
                </div>
                <div class="qei-breakdown-row">
                    <div class="qei-breakdown-label">Saturation Level</div>
                    <div class="qei-breakdown-val">{sat_pct:.2f}%</div>
                </div>
            '''
        else:
            m0_card = f'<div style="{na_style};padding:16px 0">N/A — M0 calibration data not provided.<br>Module gracefully degraded to UNKNOWN.</div>'

        # Build Control-Label card content
        if cl_v != "UNKNOWN":
            cl_text = cl_reason if cl_reason else "BIDS Control-Label ordering verified. No unexpected swaps detected."
            cl_card = f'<div style="font-size:14px;color:{COLORS["text_muted"]};line-height:1.6">{cl_text}</div>'
        else:
            cl_card = f'<div style="{na_style};padding:16px 0">N/A — ASL context/JSON not provided.<br>Module gracefully degraded to UNKNOWN.</div>'

        vstyle = VERDICT_STYLE.get(v, VERDICT_STYLE["UNKNOWN"])

        # Embedded brain images (base64 PNGs — optional, only if provided)
        imgs = r.get("images", {})
        has_images = bool(imgs)

        if has_images:
            # Row 1: CBF slice + Tissue overlay + QEI radar
            # Row 2: Tri-plane (full width, if available)
            # Row 3: CBF histogram + Timecourse
            # Row 4: FWD timeseries (full width, if available)
            # Row 5: Motion params (full width, if available)
            row1 = '<div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:0">'
            row1 += f'<img src="data:image/png;base64,{imgs.get("cbf_slice","")}" alt="CBF Map" style="width:100%;height:auto;display:block;border-right:1px solid {COLORS["border"]};border-bottom:1px solid {COLORS["border"]}">'
            row1 += f'<img src="data:image/png;base64,{imgs.get("tissue_overlay","")}" alt="Tissue Masks" style="width:100%;height:auto;display:block;border-right:1px solid {COLORS["border"]};border-bottom:1px solid {COLORS["border"]}">'
            row1 += f'<img src="data:image/png;base64,{imgs.get("qei_radar","")}" alt="QEI Radar" style="width:100%;height:auto;display:block;border-bottom:1px solid {COLORS["border"]}">'
            row1 += '</div>'

            row2 = ''
            if imgs.get('triplane'):
                row2 = f'<img src="data:image/png;base64,{imgs["triplane"]}" alt="Tri-Plane" style="width:100%;height:auto;display:block;border-bottom:1px solid {COLORS["border"]}">'

            row3 = '<div style="display:grid; grid-template-columns:1fr 1fr; gap:0">'
            row3 += f'<img src="data:image/png;base64,{imgs.get("cbf_histogram","")}" alt="CBF Histogram" style="width:100%;height:auto;display:block;border-right:1px solid {COLORS["border"]};border-bottom:1px solid {COLORS["border"]}">'
            row3 += f'<img src="data:image/png;base64,{imgs.get("timecourse","")}" alt="Timecourse" style="width:100%;height:auto;display:block;border-bottom:1px solid {COLORS["border"]}">'
            row3 += '</div>'

            row4 = ''
            if imgs.get('fwd_timeseries'):
                row4 = f'<img src="data:image/png;base64,{imgs["fwd_timeseries"]}" alt="FWD Timeseries" style="width:100%;height:auto;display:block;border-bottom:1px solid {COLORS["border"]}">'

            row5 = ''
            if imgs.get('motion_params'):
                row5 = f'<img src="data:image/png;base64,{imgs["motion_params"]}" alt="Motion Params" style="width:100%;height:auto;display:block">'

            img_html = f'<div class="card" style="padding:0; overflow:hidden; margin-bottom:24px; background:{COLORS["card"]}">{row1}{row2}{row3}{row4}{row5}</div>'
        else:
            img_html = ""

        deep_dives += f"""
        <div id="detail-{sid}" class="subject-detail-container" style="display:none; padding-top:24px;">
            <div style="display:flex; justify-content:space-between; align-items:flex-start">
                <div>
                    <div style="display:flex; gap:16px; align-items:center; margin-bottom:16px">
                        <span class="subject-header-pill" style="color:{vstyle['color']}; background:{vstyle['bg']}">
                            <span style="font-size:14px">&bull;</span> STATUS: {v}
                        </span>
                        <span style="font-size:14px; color:{COLORS['text_muted']}">Subject ID: <strong style="color:{COLORS['text_main']}">{sid}</strong> &bull; Session: 01</span>
                    </div>
                    <h1 class="subject-huge-title">Participant Quality Report</h1>
                    <p class="subject-desc">Detailed clinical verification for arterial spin labeling (ASL) perfusion datasets. Automated metrics evaluate signal fidelity and motion contamination.</p>
                </div>
                <div class="global-score-container">
                    <div class="global-score-val">{qei_val:.2f}</div>
                    <div class="global-score-label">Global QEI Score</div>
                </div>
            </div>

            {img_html}

            <div class="grid-23" style="margin-top:24px">
                <div>
                    <div class="grid-half">
                        <div class="card">
                            <div class="card-title" style="margin-bottom:24px">Motion Metrics</div>
                            {motion_card}
                        </div>
                        <div class="card">
                            <div class="card-title" style="margin-bottom:24px">SNR / sCoV Profile</div>
                            {snr_card}
                        </div>
                        <div class="card">
                            <div class="card-title" style="margin-bottom:24px">Calibration Info</div>
                            {m0_card}
                        </div>
                        <div class="card">
                            <div class="card-title" style="margin-bottom:24px">Sequence Validation</div>
                            {cl_card}
                        </div>
                    </div>
                </div>

                <div>
                    <div class="card">
                        <div class="card-title" style="margin-bottom:24px">QEI Breakdown</div>
                        <div class="qei-breakdown-row">
                            <div class="qei-breakdown-label">Structural Similarity</div>
                            <div style="flex:1; margin: 0 16px">{_progress(pss, 1.0, COLORS['primary'])}</div>
                            <div class="qei-breakdown-val">{pss:.2f}</div>
                        </div>
                        <div class="qei-breakdown-row">
                            <div class="qei-breakdown-label">Spatial Variability</div>
                            <div style="flex:1; margin: 0 16px">{_progress(min(di,1.0), 1.0, COLORS['primary'])}</div>
                            <div class="qei-breakdown-val">{di:.2f}</div>
                        </div>
                        <div class="qei-breakdown-row">
                            <div class="qei-breakdown-label">Negative Fraction</div>
                            <div style="flex:1; margin: 0 16px">{_progress(neg, 1.0, COLORS['primary'])}</div>
                            <div class="qei-breakdown-val">{neg:.2f}</div>
                        </div>
                    </div>

                    <div class="card">
                        <div style="font-size:11px; font-weight:700; color:{COLORS['text_muted']}; letter-spacing:1px; margin-bottom:16px">MODULE CHECKLIST</div>
                        {checklist}
                    </div>
                </div>
            </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>QC-ToolBox V1.0</title>
    <style>{_css()}</style>
    <script>{_js()}</script>
</head>
<body>
    <div class="layout">
        <div class="sidebar">
            <div class="logo-container">
                <div class="logo-icon"><img src="data:image/png;base64,{_load_icon_b64()}" alt="OSIPI"></div>
                <div>
                    <div class="logo-text-title">OSIPI</div>
                    <div class="logo-text-sub">QC-TOOLBOX V1.0</div>
                </div>
            </div>

            <div class="sidebar-nav">
                <a class="nav-item active" id="nav-overview" onclick="showOverview()">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M4 13h6v8H4v-8zm0-9h6v6H4V4zm8 0h8v8h-8V4zm0 10h8v6h-8v-6z"/></svg>
                    Overview
                </a>
                <a class="nav-item" id="nav-detail">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3v18M3 12h18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
                    Participant Reports
                </a>
            </div>

            <div style="margin-top:16px; border-top: 1px solid {COLORS['border']}; padding-top:16px">
                <div style="font-size:10px; font-weight:700; color:{COLORS['text_muted']}; letter-spacing:1px; margin-bottom:12px; padding:0 16px">PARTICIPANTS</div>
                {sidebar_participants}
            </div>

            <div style="margin-top:auto; padding-top:16px">
                <button class="btn btn-primary" onclick="newAnalysis()" style="width:100%; justify-content:center; background:#A43122; color:white">New Analysis</button>
            </div>
        </div>

        <!-- New Analysis Modal -->
        <div id="analysis-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:9999; align-items:center; justify-content:center">
            <div style="background:white; border-radius:16px; padding:40px; max-width:500px; width:90%; box-shadow:0 24px 80px rgba(0,0,0,0.2)">
                <h2 style="font-size:20px; margin-bottom:16px; color:{COLORS['text_main']}">Run New Analysis</h2>
                <p style="font-size:14px; color:{COLORS['text_muted']}; line-height:1.7; margin-bottom:24px">Use the CLI or Python API to run QC on your dataset:</p>
                <pre style="background:{COLORS['sidebar']}; padding:16px; border-radius:8px; font-size:12px; overflow-x:auto; margin-bottom:16px; border:1px solid {COLORS['border']}"><code># CLI
python generate_report.py

# Python API
from osipy_qc import run_qc
result = run_qc(data)</code></pre>
                <p style="font-size:12px; color:{COLORS['text_muted']}; margin-bottom:24px">See <a href="https://github.com/Jitmisra/osipy-qc" style="color:{COLORS['primary']}">README</a> for full documentation.</p>
                <button onclick="newAnalysis()" class="btn btn-outline" style="width:100%; justify-content:center">Close</button>
            </div>
        </div>

        <div class="main-content">
            <!-- Global Topbar area -->
            <div id="view-overview" style="display:block;">
                <div class="topbar">
                    <div class="topbar-left">
                        <div class="topbar-title">QC-ToolBox V1.0</div>
                        <select id="organ-selector" style="
                            padding: 5px 28px 5px 10px;
                            font-size: 12px;
                            font-weight: 600;
                            border: 1px solid {COLORS['border']};
                            border-radius: 6px;
                            background: {COLORS['card']};
                            color: {COLORS['text_main']};
                            cursor: pointer;
                            appearance: none;
                            -webkit-appearance: none;
                            background-image: url('data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%2212%22%20viewBox%3D%220%200%2012%2012%22%3E%3Cpath%20fill%3D%22%23666%22%20d%3D%22M6%208L1%203h10z%22%2F%3E%3C%2Fsvg%3E');
                            background-repeat: no-repeat;
                            background-position: right 8px center;
                        " onchange="if(this.value!=='brain'){{alert('Multi-organ QC modules ('+this.value+') are planned for GSoC 2026.');this.value='brain';}}">
                            <option value="brain" selected>Brain</option>
                            <option value="kidney" style="color:#999">Kidney (planned)</option>
                            <option value="placenta" style="color:#999">Placenta (planned)</option>
                            <option value="preclinical" style="color:#999">Preclinical (planned)</option>
                        </select>
                    </div>
                    <div class="topbar-links">
                        <a class="topbar-link active">Dashboard</a>
                        <a class="topbar-link" onclick="alert('Project views are planned for GSoC 2026.')">Projects</a>
                        <a class="topbar-link" onclick="alert('Archiving is planned for GSoC 2026.')">Archive</a>
                    </div>
                </div>

                <div class="page-container">
                    <div class="page-header">
                        <div>
                            <div class="page-title">Batch Overview</div>
                            <div class="page-subtitle">Dataset: {dataset_name} &bull; {n_total} Active Participants</div>
                        </div>
                        <div style="display:flex;gap:12px;flex-wrap:wrap">
                            <button class="btn btn-outline" onclick="alert('Advanced filtering is planned for GSoC 2026.')">Filter</button>
                            <button class="btn btn-primary" onclick="exportReport()">Export Report</button>
                        </div>
                    </div>

                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-tag" style="color:{COLORS['text_muted']}">AGGREGATE</div>
                            <div class="stat-title">Total Scans</div>
                            <div class="stat-value">{n_total}</div>
                            <div style="font-size:11px; font-weight:600; color:{COLORS['text_muted']}">Analyzed Cohort</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-tag" style="color:{COLORS['pass']}">OPTIMAL</div>
                            <div class="stat-title">Pass Rate</div>
                            <div class="stat-value">{pass_rate:.0f}<span>%</span></div>
                            {_progress(pass_rate, 100, COLORS['pass'])}
                        </div>
                        <div class="stat-card">
                            <div class="stat-tag" style="color:{COLORS['warn']}">MODERATE</div>
                            <div class="stat-title">Warning</div>
                            <div class="stat-value">{warn_rate:.0f}<span>%</span></div>
                            {_progress(warn_rate, 100, COLORS['warn'])}
                        </div>
                        <div class="stat-card">
                            <div class="stat-tag" style="color:{COLORS['fail']}">CRITICAL</div>
                            <div class="stat-title">Fail Rate</div>
                            <div class="stat-value">{fail_rate:.0f}<span>%</span></div>
                            {_progress(fail_rate, 100, COLORS['fail'])}
                        </div>
                    </div>

                    <div class="grid-23">
                        <div class="card">
                            <div class="card-header">
                                <div class="card-title">Participant Ledger</div>
                                <div style="font-size:11px; background:{COLORS['bar_bg']}; padding:4px 10px; border-radius:12px; font-weight:600">ACTIVE FILTERS: NONE</div>
                            </div>
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>Participant ID</th>
                                        <th>Verdict</th>
                                        <th>QEI Score</th>
                                        <th>Primary Artifact</th>
                                        <th>Action</th>
                                    </tr>
                                </thead>
                                <tbody>{ledger_rows}</tbody>
                            </table>
                        </div>
                        <div class="card">
                            <div style="font-size:11px; font-weight:700; color:{COLORS['text_muted']}; letter-spacing:1px; margin-bottom:24px">ARTIFACT BREAKDOWN</div>
                            {artifact_html}

                            <div style="margin-top:32px; background:#FAF2ED; padding:16px; border-radius:8px; border:1px solid #EEDFCA">
                                <div style="font-weight:600; font-size:13px; margin-bottom:8px; color:{COLORS['primary']}">&#128161; Batch Insight</div>
                                <div style="font-size:12px; color:{COLORS['text_muted']}">Analysis of <strong>{n_total}</strong> subjects completed. The current cohort exhibits a <strong>{pass_rate:.1f}%</strong> pass rate based on the '{config_name}' quality profile thresholds.</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Details View Shell -->
            <div id="view-detail" style="display:none;">
                <div class="topbar">
                    <div class="topbar-left">
                        <div class="topbar-title">QC-ToolBox V1.0</div>
                    </div>
                    <div class="topbar-links">
                        <a class="topbar-link active" onclick="showOverview()" style="cursor:pointer">&larr; Subject Deep Dive</a>
                        <a class="topbar-link" id="topbar-subject-id"></a>
                    </div>
                </div>
                <div class="page-container" id="detail-container">
                    {deep_dives}
                </div>
            </div>

        </div>
    </div>
</body>
</html>
"""
