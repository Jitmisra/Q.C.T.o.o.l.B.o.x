#!/usr/bin/env python3
"""
derive_thresholds.py — Derive cohort-level QC thresholds from qc_results.csv.

Runs three statistical methods (IQR, GMM, KDE) on each metric and produces
publication-quality comparison plots, a markdown report, and a JSON report.

Usage:
    python scripts/derive_thresholds.py \\
        --csv qc_output/qc_results.csv \\
        --output qc_output/threshold_analysis

Outputs:
    <output>/qei_thresholds.png
    <output>/spatial_cov_thresholds.png
    <output>/threshold_report.md
    <output>/threshold_report.json
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

# Allow running from project root
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from osipy_qc.threshold import (  # noqa: E402
    ThresholdReport,
    export_threshold_report,
    plot_threshold_comparison,
)

# Metrics that can be derived. Default: QEI + spatial_cov.
KNOWN_METRICS = {
    "qei":         ("QEI",                  True),   # higher = better
    "spatial_cov": ("Spatial CoV (%)",      False),  # lower = better
    "pss":         ("Structural Similarity", True),
    "snr":         ("Signal-to-Noise Ratio", True),
    "mean_fwd":    ("Mean FWD (mm)",        False),
}
DEFAULT_METRICS = ("qei", "spatial_cov")


def load_column(csv_path: Path, column: str) -> np.ndarray:
    """Load a single numeric column from a CSV file."""
    vals: list[float] = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or column not in reader.fieldnames:
            raise KeyError(f"Column '{column}' not found in {csv_path}")
        for row in reader:
            try:
                x = float(row[column])
                if np.isfinite(x):
                    vals.append(x)
            except (TypeError, ValueError):
                continue
    return np.asarray(vals, dtype=float)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Derive cohort QC thresholds (IQR + GMM + KDE)"
    )
    ap.add_argument("--csv", type=Path, required=True,
                    help="Path to qc_results.csv")
    ap.add_argument("--output", type=Path, required=True,
                    help="Output directory for plots and reports")
    ap.add_argument("--metrics", nargs="*", default=list(DEFAULT_METRICS),
                    help=f"Metrics to derive (choices: {', '.join(KNOWN_METRICS)})")
    ap.add_argument("--seed", type=int, default=0,
                    help="Random seed for GMM (default: 0)")
    args = ap.parse_args()

    csv_path = args.csv.resolve()
    out_dir = args.output.resolve()

    if not csv_path.is_file():
        print(f"Error: {csv_path} not found", file=sys.stderr)
        return 1

    unknown = set(args.metrics) - set(KNOWN_METRICS)
    if unknown:
        print(f"Error: unknown metrics: {unknown}", file=sys.stderr)
        return 1

    reports: list[ThresholdReport] = []

    for key in args.metrics:
        label, higher_is_better = KNOWN_METRICS[key]
        try:
            values = load_column(csv_path, key)
        except KeyError as e:
            print(f"  Skip {key}: {e}", file=sys.stderr)
            continue
        if values.size < 10:
            print(f"  Skip {key}: only {values.size} values (need ≥10)")
            continue

        print(f"  Deriving thresholds for {label} (n={values.size})...")
        report = plot_threshold_comparison(
            values, label, out_dir / f"{key}_thresholds.png",
            higher_is_better=higher_is_better, seed=args.seed,
        )
        reports.append(report)
        print(f"    GMM={report.gmm.threshold:.4f}  "
              f"KDE={report.kde.threshold:.4f}  "
              f"IQR=[{report.iqr.lower_fence:.4f}, {report.iqr.upper_fence:.4f}]  "
              f"★ {report.recommended_method}={report.recommended_threshold:.4f}")

    if not reports:
        print("No metrics could be derived.", file=sys.stderr)
        return 1

    export_threshold_report(reports, out_dir)
    print(f"\n  Reports saved to: {out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
