"""
registry.py — Module registry following osipy's @register_*(name) pattern.

The osipy library uses a consistent decorator-based registry throughout:
    @register_quantification_model("pcasl_single_pld")
    @register_m0_calibration("voxelwise")

This module mirrors that exact convention for QC checks:
    @register_qc_check("qei")
    @register_qc_check("motion")

Each registered module must implement BaseQCCheck with a `run()` method
that returns a ModuleResult.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from osipy_qc.verdict import Verdict

# ---------------------------------------------------------------------------
# Module result container
# ---------------------------------------------------------------------------

@dataclass
class ModuleResult:
    """Standardized result from any QC module."""

    name: str
    verdict: Verdict
    metrics: dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "verdict": self.verdict.value,
            "metrics": self.metrics,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class BaseQCCheck(ABC):
    """
    Abstract base for all QC modules.

    Subclasses must implement ``run()`` and declare ``required_inputs``
    so the orchestrator knows what data each module needs.
    """

    # Override in subclass: list of keys this module needs
    # e.g. ["cbf_map", "gm_prob", "wm_prob"]
    required_inputs: list[str] = []

    @abstractmethod
    def run(self, data: dict[str, Any], config: dict[str, Any]) -> ModuleResult:
        """
        Execute the QC check.

        Parameters
        ----------
        data : dict
            Available data keyed by name (e.g. "cbf_map", "gm_prob",
            "asl_4d", "motion_params", "asl_json", etc).
        config : dict
            Threshold/parameter config for this module.

        Returns
        -------
        ModuleResult with verdict and metrics.
        """
        ...

    def can_run(self, data: dict[str, Any]) -> bool:
        """Check if all required inputs are available."""
        return all(k in data and data[k] is not None for k in self.required_inputs)


# ---------------------------------------------------------------------------
# Registry (matches osipy's get_*/list_* pattern)
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[BaseQCCheck]] = {}


def register_qc_check(name: str):
    """
    Decorator to register a QC module.

    Mirrors osipy's @register_quantification_model(name) convention.

    Example
    -------
    >>> @register_qc_check("qei")
    ... class QEICheck(BaseQCCheck):
    ...     def run(self, data, config):
    ...         ...
    """
    def decorator(cls: type[BaseQCCheck]) -> type[BaseQCCheck]:
        if name in _REGISTRY:
            raise ValueError(f"QC check '{name}' is already registered")
        if not issubclass(cls, BaseQCCheck):
            raise TypeError(
                f"{cls.__name__} must subclass BaseQCCheck"
            )
        _REGISTRY[name] = cls
        return cls
    return decorator


def get_qc_check(name: str) -> BaseQCCheck:
    """Instantiate a registered QC check by name."""
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(
            f"Unknown QC check '{name}'. Available: {available}"
        )
    return _REGISTRY[name]()


def list_qc_checks() -> list[str]:
    """Return sorted list of all registered QC check names."""
    return sorted(_REGISTRY.keys())
