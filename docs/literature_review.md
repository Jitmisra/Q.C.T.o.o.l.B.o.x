# Literature Review: ASL Perfusion Quality Control

This document surveys the key publications underlying each QC module in
`osipy-qc`. Understanding the evidence base is critical for setting
defensible thresholds and extending the toolbox to new organs and populations.

---

## 1. QEI — Quality Evaluation Index

**Dolui S et al. (2024).** *"Quality Evaluation Index for ASL CBF Maps."*
Journal of Magnetic Resonance Imaging (JMRI).

The QEI is the geometric mean of three normalized sub-metrics:

| Component | Abbreviation | What It Captures |
|---|---|---|
| Structural Similarity | PSS | Spatial correlation between CBF and GM probability |
| Spatial Variability | DI (Detectability Index) | Abnormal heterogeneity within GM voxels |
| Negative Voxel Fraction | Neg | Proportion of physiologically impossible negative CBF |

**Our takeaway:** QEI is the best single-number summary of ASL image quality.
We use it as the anchor metric. The geometric mean ensures that a catastrophic
failure in *any one* component collapses the overall score — which is the
correct behavior for a triage tool.

---

## 2. Frame-wise Displacement

**Power JD et al. (2012).** *"Spurious but systematic correlations in
functional connectivity MRI networks arise from subject motion."*
NeuroImage, 59(3): 2142-2154.

Introduced the 0.5mm FWD threshold for scrubbing motion-contaminated volumes.
This has become the de-facto standard across fMRI and ASL pipelines.

**Our takeaway:** We use Power's FWD formula (sum of absolute derivatives
of the 6 rigid-body parameters, with rotations converted to mm at a 50mm
head radius). We apply the 0.5mm threshold for healthy adults but relax to
1.2mm for elderly populations (see `stroke_elderly.yaml`).

---

## 3. Spatial Coefficient of Variation (sCoV)

**Mutsaerts HJ et al. (2017).** *"The spatial coefficient of variation in
ASL cerebral blood flow images."* JCBFM, 37(9): 3184-3192.

sCoV = 100 × σ/μ within GM. Reported: **56.9 ± 13.2%** in 186 elderly
patients (mean age 78.2). Higher sCoV indicates greater perfusion
heterogeneity, which correlates with transit-time effects and noise.

**Our takeaway:** sCoV is the most reproducible single voxel-wise metric for
ASL quality. We set `warn_above: 70%` (≈ mean + 1 SD from Mutsaerts) for
adults and `warn_above: 83%` (≈ mean + 2 SD) for elderly. This ensures
clinical data isn't over-excluded.

---

## 4. PCASL Acquisition Consensus

**Alsop DC et al. (2015).** *"Recommended implementation of arterial
spin-labeled perfusion MRI for clinical applications."*
Magnetic Resonance in Medicine, 73(1): 102-116.

This white paper is the primary reference for PCASL acquisition parameters.
Key population-specific PLD recommendations:

| Population | Recommended PLD |
|---|---|
| Children | 1,500 ms |
| Healthy adults (< 70 y) | 1,800 ms |
| Healthy adults (> 70 y) | 2,000 ms |
| Neonates | 2,000 ms |

**Our takeaway:** PLD affects transit-time artifacts. Our `m0_check` module
validates TR (≥ 4s per Alsop) and our population configs set different
thresholds based on the expected PLD/ATT for each group.

---

## 5. Renal ASL Consensus

**Nery F et al. (2020).** *"Consensus-based technical recommendations
for clinical translation of renal ASL MRI."*
MAGMA, 33: 141-161. doi: 10.1007/s10334-019-00823-y

The PARENCHIMA (Cost Action) consortium established reference ranges for
renal perfusion:

| Region | Expected CBF | Notes |
|---|---|---|
| Renal cortex | 250-350 mL/100g/min | Healthy adults |
| Renal medulla | 30-120 mL/100g/min | Highly variable |
| Cortex/medulla ratio | 3:1 to 5:1 | Primary QC indicator |
| CKD patients | Ratio < 2:1 | Cortical hypoperfusion |

FAIR (Flow-sensitive Alternating Inversion Recovery) is recommended over
PCASL for kidneys due to the organ's position relative to the labeling plane.

**Our takeaway:** We implemented these thresholds directly in the
`renal_cortex_medulla` module and `kidney_fair.yaml` config. The cortex/medulla
ratio is the primary quality indicator — anatomically equivalent to GM/WM
contrast in the brain.

---

## 6. Multi-Organ ASL Challenges

**Mora Álvarez MG et al. (2024).** *"Quantitative non-contrast perfusion
MRI of the body."* MAGMA — Review of ASL techniques across kidneys,
liver, pancreas, placenta, and other organs.

Key challenges identified:
- Different organs require different labeling planes
- Respiratory motion dominates (vs. head motion in brain)
- T1 of blood varies with hematocrit (critical in neonates and anemia)
- No universal QC metric exists; each organ needs tailored checks

**Our takeaway:** This paper (by our project mentor) directly motivates the
registry-based architecture of `osipy-qc`. Each organ gets its own YAML config
that selects which modules to run and sets organ-appropriate thresholds. The
`@register_qc_check` pattern makes adding new organ-specific modules
straightforward without modifying core pipeline code.

---

## 7. OSIPI PyASL Library

**OSIPI Task Force 2.2 (2025).** *"PyASL: A composite Python library for
ASL preprocessing and analysis."* Presented at ISMRM 2025.

Repository: [github.com/OSIPI/TF2.2_OSIPI-ASL-toolbox](https://github.com/OSIPI/TF2.2_OSIPI-ASL-toolbox)

PyASL provides standardized preprocessing (motion correction, registration,
CBF quantification) for both human and preclinical ASL data.

**Our takeaway:** `osipy-qc` is designed as a downstream consumer of PyASL
output. Our pipeline takes already-quantified CBF maps and applies quality
checks — we don't duplicate PyASL's preprocessing. The `@register_qc_check`
pattern mirrors osipy's own `@register_*` / `get_*` / `list_*` conventions
to ensure seamless integration during GSoC.
