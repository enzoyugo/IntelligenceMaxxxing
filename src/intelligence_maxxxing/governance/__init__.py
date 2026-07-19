"""Governance utilities. Stage 0 implements constitutional manifest verification.

Method lifecycle, promotion policy and kill-switch logic (ENGINE_GOVERNANCE.md)
are deferred; nothing here simulates them.
"""

from intelligence_maxxxing.governance.manifest import (
    ManifestEntry,
    ManifestVerification,
    compute_manifest,
    verify_manifest,
)

__all__ = ["ManifestEntry", "ManifestVerification", "compute_manifest", "verify_manifest"]
