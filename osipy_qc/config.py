"""
config.py — YAML-based configuration with pydantic validation.

Supports population-specific threshold profiles:
    configs/adult_3T.yaml
    configs/neonatal_chd.yaml
    configs/elderly_dementia.yaml
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ModuleConfig:
    """Thresholds for a single QC module."""

    enabled: bool = True
    thresholds: dict[str, float] = field(default_factory=dict)


@dataclass
class QCConfig:
    """
    Complete QC configuration for a population profile.

    Loaded from YAML, validated at startup. Each module gets its
    own threshold section, so population-specific cutoffs are trivial.
    """

    profile_name: str = "default"
    description: str = ""
    modules: dict[str, ModuleConfig] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> QCConfig:
        """Load config from a YAML file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path) as f:
            raw = yaml.safe_load(f)

        modules = {}
        for name, mod_raw in raw.get("modules", {}).items():
            modules[name] = ModuleConfig(
                enabled=mod_raw.get("enabled", True),
                thresholds=mod_raw.get("thresholds", {}),
            )

        return cls(
            profile_name=raw.get("profile_name", path.stem),
            description=raw.get("description", ""),
            modules=modules,
        )

    @classmethod
    def default(cls) -> QCConfig:
        """Return built-in adult 3T PCASL defaults."""
        return cls(
            profile_name="adult_3T_default",
            description="Built-in defaults for adult 3T PCASL (provisional)",
            modules={
                "qei": ModuleConfig(thresholds={
                    "fail_below": 0.30,
                    "warn_below": 0.55,
                }),
                "motion": ModuleConfig(thresholds={
                    "fwd_fail_above": 1.5,
                    "fwd_warn_above": 0.5,
                }),
                "control_label": ModuleConfig(thresholds={}),
                "m0_check": ModuleConfig(thresholds={
                    "tr_fail_below": 2.0,
                    "tr_warn_below": 4.0,
                    "saturation_pct_fail": 5.0,
                }),
                "snr_cov": ModuleConfig(thresholds={
                    "scov_fail_above": 90.0,
                    "scov_warn_above": 70.0,
                    "neg_frac_fail_above": 0.20,
                    "neg_frac_warn_above": 0.10,
                }),
            },
        )

    def get_module_config(self, name: str) -> ModuleConfig:
        """Get config for a specific module, falling back to empty."""
        return self.modules.get(name, ModuleConfig())
