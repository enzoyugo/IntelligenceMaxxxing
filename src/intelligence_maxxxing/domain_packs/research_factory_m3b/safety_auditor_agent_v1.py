"""SafetyAuditorAgentV1 — informs only; never kills processes or mutates config."""

from __future__ import annotations

from typing import Any

from intelligence_maxxxing.domain_packs.research_factory_m3a.hashes import content_hash, new_id, utc_now
from intelligence_maxxxing.domain_packs.research_factory_m3b.constants import (
    CRITICAL_SAFETY_FAILURE_CODES,
    M3B_ID,
    M3B_VERSION,
    SAFETY_AUDIT_SCHEMA,
)

AGENT_ID = "SafetyAuditorAgentV1"
AGENT_VERSION = "1.0.0"


def _probe(payload: dict[str, Any], key: str) -> Any:
    """Return probe value or a sentinel indicating UNKNOWN (key absent)."""
    if key not in payload:
        return _UNKNOWN
    return payload.get(key)


_UNKNOWN = object()


def _check(
    *,
    check_id: str,
    category: str,
    status: str,
    detail: str,
    critical: bool = False,
    code: str | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "category": category,
        "status": status,
        "detail": detail,
        "critical": critical,
        "failure_code": code,
    }


class SafetyAuditorAgentV1:
    agent_id = AGENT_ID
    agent_version = AGENT_VERSION

    def audit(self, scope_payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(scope_payload, dict):
            raise ValueError("scope_payload must be a dict")

        checks: list[dict[str, Any]] = []

        # --- Boundaries ---
        broker = _probe(scope_payload, "broker_calls")
        if broker is _UNKNOWN:
            checks.append(
                _check(
                    check_id="boundary.broker_calls",
                    category="BOUNDARY",
                    status="UNKNOWN",
                    detail="broker_calls probe not provided",
                    critical=True,
                    code="BROKER_CALLS_DETECTED",
                )
            )
        elif int(broker or 0) > 0:
            checks.append(
                _check(
                    check_id="boundary.broker_calls",
                    category="BOUNDARY",
                    status="FAIL",
                    detail=f"broker_calls={broker}",
                    critical=True,
                    code="BROKER_CALLS_DETECTED",
                )
            )
        else:
            checks.append(
                _check(
                    check_id="boundary.broker_calls",
                    category="BOUNDARY",
                    status="PASS",
                    detail="broker_calls=0",
                )
            )

        tmx = _probe(scope_payload, "tmx_storage_access")
        if tmx is _UNKNOWN:
            checks.append(
                _check(
                    check_id="boundary.tmx_storage",
                    category="BOUNDARY",
                    status="UNKNOWN",
                    detail="tmx_storage_access probe not provided",
                    critical=True,
                    code="TMX_STORAGE_ACCESS",
                )
            )
        elif bool(tmx):
            checks.append(
                _check(
                    check_id="boundary.tmx_storage",
                    category="BOUNDARY",
                    status="FAIL",
                    detail="tmx_storage_access=true",
                    critical=True,
                    code="TMX_STORAGE_ACCESS",
                )
            )
        else:
            checks.append(
                _check(
                    check_id="boundary.tmx_storage",
                    category="BOUNDARY",
                    status="PASS",
                    detail="tmx_storage_access=false",
                )
            )

        ollama = _probe(scope_payload, "ollama_invoked")
        if ollama is _UNKNOWN:
            checks.append(
                _check(
                    check_id="boundary.ollama",
                    category="BOUNDARY",
                    status="UNKNOWN",
                    detail="ollama_invoked probe not provided",
                    critical=True,
                    code="OLLAMA_INVOKED",
                )
            )
        elif bool(ollama):
            checks.append(
                _check(
                    check_id="boundary.ollama",
                    category="BOUNDARY",
                    status="FAIL",
                    detail="ollama_invoked=true",
                    critical=True,
                    code="OLLAMA_INVOKED",
                )
            )
        else:
            checks.append(
                _check(
                    check_id="boundary.ollama",
                    category="BOUNDARY",
                    status="PASS",
                    detail="ollama_invoked=false",
                )
            )

        # --- Temporality / leakage ---
        oos = _probe(scope_payload, "oos_rows_read")
        if oos is _UNKNOWN:
            checks.append(
                _check(
                    check_id="temporality.oos_rows_read",
                    category="TEMPORALITY",
                    status="UNKNOWN",
                    detail="oos_rows_read probe not provided",
                    critical=True,
                    code="OOS_ROWS_READ",
                )
            )
        elif int(oos or 0) > 0:
            checks.append(
                _check(
                    check_id="temporality.oos_rows_read",
                    category="TEMPORALITY",
                    status="FAIL",
                    detail=f"oos_rows_read={oos}",
                    critical=True,
                    code="OOS_ROWS_READ",
                )
            )
        else:
            checks.append(
                _check(
                    check_id="temporality.oos_rows_read",
                    category="TEMPORALITY",
                    status="PASS",
                    detail="oos_rows_read=0",
                )
            )

        future = _probe(scope_payload, "future_feature_count")
        if future is _UNKNOWN:
            checks.append(
                _check(
                    check_id="temporality.future_features",
                    category="TEMPORALITY",
                    status="UNKNOWN",
                    detail="future_feature_count probe not provided",
                    critical=True,
                    code="FUTURE_FEATURES_DETECTED",
                )
            )
        elif int(future or 0) > 0:
            checks.append(
                _check(
                    check_id="temporality.future_features",
                    category="TEMPORALITY",
                    status="FAIL",
                    detail=f"future_feature_count={future}",
                    critical=True,
                    code="FUTURE_FEATURES_DETECTED",
                )
            )
        else:
            checks.append(
                _check(
                    check_id="temporality.future_features",
                    category="TEMPORALITY",
                    status="PASS",
                    detail="future_feature_count=0",
                )
            )

        leakage = _probe(scope_payload, "outcome_leakage_count")
        if leakage is _UNKNOWN:
            checks.append(
                _check(
                    check_id="temporality.outcome_leakage",
                    category="TEMPORALITY",
                    status="UNKNOWN",
                    detail="outcome_leakage_count probe not provided",
                    critical=True,
                    code="OUTCOME_LEAKAGE",
                )
            )
        elif int(leakage or 0) > 0:
            checks.append(
                _check(
                    check_id="temporality.outcome_leakage",
                    category="TEMPORALITY",
                    status="FAIL",
                    detail=f"outcome_leakage_count={leakage}",
                    critical=True,
                    code="OUTCOME_LEAKAGE",
                )
            )
        else:
            checks.append(
                _check(
                    check_id="temporality.outcome_leakage",
                    category="TEMPORALITY",
                    status="PASS",
                    detail="outcome_leakage_count=0",
                )
            )

        # --- Experiments / research factory ---
        auto_run = _probe(scope_payload, "auto_run")
        if auto_run is _UNKNOWN:
            checks.append(
                _check(
                    check_id="experiments.auto_run",
                    category="EXPERIMENTS",
                    status="UNKNOWN",
                    detail="auto_run probe not provided",
                    critical=True,
                    code="AUTO_RUN_ENABLED",
                )
            )
        elif bool(auto_run):
            checks.append(
                _check(
                    check_id="experiments.auto_run",
                    category="EXPERIMENTS",
                    status="FAIL",
                    detail="auto_run=true",
                    critical=True,
                    code="AUTO_RUN_ENABLED",
                )
            )
        else:
            checks.append(
                _check(
                    check_id="experiments.auto_run",
                    category="EXPERIMENTS",
                    status="PASS",
                    detail="auto_run=false",
                )
            )

        auto_promo = _probe(scope_payload, "auto_promotion")
        if auto_promo is _UNKNOWN:
            checks.append(
                _check(
                    check_id="experiments.auto_promotion",
                    category="EXPERIMENTS",
                    status="UNKNOWN",
                    detail="auto_promotion probe not provided",
                    critical=True,
                    code="AUTO_PROMOTION_ENABLED",
                )
            )
        elif bool(auto_promo):
            checks.append(
                _check(
                    check_id="experiments.auto_promotion",
                    category="EXPERIMENTS",
                    status="FAIL",
                    detail="auto_promotion=true",
                    critical=True,
                    code="AUTO_PROMOTION_ENABLED",
                )
            )
        else:
            checks.append(
                _check(
                    check_id="experiments.auto_promotion",
                    category="EXPERIMENTS",
                    status="PASS",
                    detail="auto_promotion=false",
                )
            )

        manual = _probe(scope_payload, "manual_approval_required")
        if manual is _UNKNOWN:
            checks.append(
                _check(
                    check_id="research_factory.manual_approval",
                    category="RESEARCH_FACTORY",
                    status="UNKNOWN",
                    detail="manual_approval_required probe not provided",
                )
            )
        elif bool(manual):
            checks.append(
                _check(
                    check_id="research_factory.manual_approval",
                    category="RESEARCH_FACTORY",
                    status="PASS",
                    detail="manual_approval_required=true",
                )
            )
        else:
            checks.append(
                _check(
                    check_id="research_factory.manual_approval",
                    category="RESEARCH_FACTORY",
                    status="WARN",
                    detail="manual_approval_required=false",
                )
            )

        m3_complete = _probe(scope_payload, "milestone_3_complete")
        if m3_complete is _UNKNOWN:
            checks.append(
                _check(
                    check_id="research_factory.milestone_3",
                    category="RESEARCH_FACTORY",
                    status="UNKNOWN",
                    detail="milestone_3_complete probe not provided",
                )
            )
        elif bool(m3_complete):
            checks.append(
                _check(
                    check_id="research_factory.milestone_3",
                    category="RESEARCH_FACTORY",
                    status="WARN",
                    detail="milestone_3_complete unexpectedly true for M3B foundation",
                )
            )
        else:
            checks.append(
                _check(
                    check_id="research_factory.milestone_3",
                    category="RESEARCH_FACTORY",
                    status="PASS",
                    detail="milestone_3_complete=false",
                )
            )

        # --- Economy honesty ---
        gross_trusted = _probe(scope_payload, "gross_trusted_separated")
        if gross_trusted is _UNKNOWN:
            checks.append(
                _check(
                    check_id="economy.gross_vs_trusted",
                    category="ECONOMY",
                    status="UNKNOWN",
                    detail="gross_trusted_separated probe not provided",
                )
            )
        elif bool(gross_trusted):
            checks.append(
                _check(
                    check_id="economy.gross_vs_trusted",
                    category="ECONOMY",
                    status="PASS",
                    detail="gross_trusted_separated=true",
                )
            )
        else:
            checks.append(
                _check(
                    check_id="economy.gross_vs_trusted",
                    category="ECONOMY",
                    status="WARN",
                    detail="gross_trusted_separated=false",
                )
            )

        # --- Runtime ---
        execution = _probe(scope_payload, "execution_enabled")
        if execution is _UNKNOWN:
            checks.append(
                _check(
                    check_id="runtime.execution_enabled",
                    category="RUNTIME",
                    status="UNKNOWN",
                    detail="execution_enabled probe not provided",
                    critical=True,
                    code="EXECUTION_ENABLED",
                )
            )
        elif bool(execution):
            checks.append(
                _check(
                    check_id="runtime.execution_enabled",
                    category="RUNTIME",
                    status="FAIL",
                    detail="execution_enabled=true",
                    critical=True,
                    code="EXECUTION_ENABLED",
                )
            )
        else:
            checks.append(
                _check(
                    check_id="runtime.execution_enabled",
                    category="RUNTIME",
                    status="PASS",
                    detail="execution_enabled=false",
                )
            )

        mutations = _probe(scope_payload, "policy_mutations")
        if mutations is _UNKNOWN:
            checks.append(
                _check(
                    check_id="runtime.policy_mutations",
                    category="RUNTIME",
                    status="UNKNOWN",
                    detail="policy_mutations probe not provided",
                    critical=True,
                    code="POLICY_MUTATION_DETECTED",
                )
            )
        elif int(mutations or 0) > 0:
            checks.append(
                _check(
                    check_id="runtime.policy_mutations",
                    category="RUNTIME",
                    status="FAIL",
                    detail=f"policy_mutations={mutations}",
                    critical=True,
                    code="POLICY_MUTATION_DETECTED",
                )
            )
        else:
            checks.append(
                _check(
                    check_id="runtime.policy_mutations",
                    category="RUNTIME",
                    status="PASS",
                    detail="policy_mutations=0",
                )
            )

        policy_frozen = _probe(scope_payload, "policy_frozen")
        if policy_frozen is _UNKNOWN:
            checks.append(
                _check(
                    check_id="runtime.policy_frozen",
                    category="RUNTIME",
                    status="UNKNOWN",
                    detail="policy_frozen probe not provided",
                )
            )
        elif bool(policy_frozen):
            checks.append(
                _check(
                    check_id="runtime.policy_frozen",
                    category="RUNTIME",
                    status="PASS",
                    detail="policy_frozen=true",
                )
            )
        else:
            checks.append(
                _check(
                    check_id="runtime.policy_frozen",
                    category="RUNTIME",
                    status="WARN",
                    detail="policy_frozen=false",
                )
            )

        bundle_frozen = _probe(scope_payload, "bundle_frozen")
        if bundle_frozen is _UNKNOWN:
            checks.append(
                _check(
                    check_id="runtime.bundle_frozen",
                    category="RUNTIME",
                    status="UNKNOWN",
                    detail="bundle_frozen probe not provided",
                )
            )
        elif bool(bundle_frozen):
            checks.append(
                _check(
                    check_id="runtime.bundle_frozen",
                    category="RUNTIME",
                    status="PASS",
                    detail="bundle_frozen=true",
                )
            )
        else:
            checks.append(
                _check(
                    check_id="runtime.bundle_frozen",
                    category="RUNTIME",
                    status="WARN",
                    detail="bundle_frozen=false",
                )
            )

        # Aggregate — UNKNOWN must never become PASS.
        critical_failures: list[str] = []
        seen: set[str] = set()
        for c in checks:
            if (
                c.get("critical")
                and c.get("status") == "FAIL"
                and c.get("failure_code") in CRITICAL_SAFETY_FAILURE_CODES
            ):
                code = str(c["failure_code"])
                if code not in seen:
                    seen.add(code)
                    critical_failures.append(code)

        n_pass = sum(1 for c in checks if c["status"] == "PASS")
        n_fail = sum(1 for c in checks if c["status"] == "FAIL")
        n_warn = sum(1 for c in checks if c["status"] == "WARN")
        n_unknown = sum(1 for c in checks if c["status"] == "UNKNOWN")
        n_critical_unknown = sum(
            1 for c in checks if c.get("critical") and c.get("status") == "UNKNOWN"
        )

        # UNKNOWN must never become PASS. Missing probes are PARTIAL, not BLOCKED.
        # BLOCKED only for explicit FAIL (or critical FAIL codes).
        if critical_failures or n_fail > 0:
            overall = "SAFETY_BLOCKED"
        elif n_unknown > 0 or n_critical_unknown > 0:
            overall = "SAFETY_PARTIAL"
        elif n_warn > 0:
            overall = "SAFETY_PASS_WITH_WARNINGS"
        elif n_pass == len(checks):
            overall = "SAFETY_PASS"
        else:
            overall = "SAFETY_PARTIAL"

        scope = {
            "scope_id": scope_payload.get("scope_id"),
            "scope_label": scope_payload.get("scope_label") or "m3b_safety_audit",
        }
        input_hash = content_hash(
            {
                "scope": scope,
                "probes": {
                    k: scope_payload.get(k)
                    for k in sorted(
                        {
                            "broker_calls",
                            "tmx_storage_access",
                            "ollama_invoked",
                            "oos_rows_read",
                            "future_feature_count",
                            "outcome_leakage_count",
                            "auto_run",
                            "auto_promotion",
                            "manual_approval_required",
                            "milestone_3_complete",
                            "gross_trusted_separated",
                            "execution_enabled",
                            "policy_mutations",
                            "policy_frozen",
                            "bundle_frozen",
                        }
                    )
                    if k in scope_payload
                },
            }
        )

        body: dict[str, Any] = {
            "schema_version": SAFETY_AUDIT_SCHEMA,
            "audit_id": new_id("SA"),
            "m3b_id": M3B_ID,
            "m3b_version": M3B_VERSION,
            "agent_id": AGENT_ID,
            "agent_version": AGENT_VERSION,
            "created_at": utc_now(),
            "scope": scope,
            "checks": checks,
            "overall_status": overall,
            "critical_failures": critical_failures,
            "counts": {
                "n_pass": n_pass,
                "n_fail": n_fail,
                "n_warn": n_warn,
                "n_unknown": n_unknown,
            },
            "informs_only": True,
            "kills_process": False,
            "mutates_config": False,
            "non_authoritative": True,
            "append_only": True,
            "research_only": True,
            "limitations": [
                "PROBE_FACTS_REQUIRED",
                "UNKNOWN_NEVER_PASS",
                "INFORMS_ONLY",
            ],
            "input_hash": input_hash,
        }
        stable = {
            k: v
            for k, v in body.items()
            if k not in {"audit_id", "created_at", "output_hash", "content_hash"}
        }
        body["content_hash"] = content_hash(stable)
        body["output_hash"] = body["content_hash"]
        return body
