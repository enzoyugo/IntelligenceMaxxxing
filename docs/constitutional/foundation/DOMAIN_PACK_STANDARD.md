# DOMAIN PACK STANDARD

**Status:** Binding extension standard  
**Version:** 1.0  
**Parent authority:** Constitution v1.1, Governance v1.0, Epistemic Standard v1.0

---

## 1. Purpose

A Domain Pack teaches the Core Engine how to understand a specific domain without duplicating the Engine's universal responsibilities.

A Domain Pack is not an application, frontend, database shortcut, or independent decision engine.

---

## 2. Required pack charter

Every pack must include a short charter declaring:

- purpose;
- problem;
- intended users;
- domain vocabulary;
- observable data;
- decisions supported;
- measurable outcomes;
- risks;
- maximum autonomy;
- protected metrics;
- limitations;
- cross-domain relationships;
- conditions for retirement.

---

## 3. Ownership and status

Initially, only the Constitutional Owner may create or admit a Domain Pack.

Pack statuses:

- `EXPERIMENTAL`
- `OFFICIAL`
- `DEGRADED`
- `SUSPENDED`
- `RETIRED`

The Engine may recommend new Domain Packs when it detects a repeated high-value need, but admission remains human-controlled.

---

## 4. Core boundary

The following always remain in the Core:

- identity;
- timestamps;
- evidence;
- hypotheses;
- beliefs;
- decisions;
- recommendations;
- outcomes;
- audit;
- permissions;
- learning;
- versioning;
- constitutional enforcement;
- cross-domain coordination.

A Domain Pack may customize:

- vocabulary;
- sources;
- features;
- experiments;
- metrics;
- models;
- risk policies;
- calibration;
- actions;
- freshness;
- sample requirements.

A pack may not reimplement Core objects under different names to bypass governance.

---

## 5. Dependencies between packs

A pack may depend on another pack only through explicit versioned contracts.

Allowed:

- Sports Betting Pack consumes evidence from Sports Data Pack.
- Life Pack consumes governed financial impact from Financial Pack.
- Cross-Domain Coordinator consumes published recommendations and constraints.

Forbidden:

- hidden imports;
- direct database reads;
- writing another pack's objects;
- silent dependency on another pack's model internals.

A pack publishes evidence; it does not directly rewrite another pack.

---

## 6. Minimum capability contract

Each pack must implement or explicitly declare non-applicability for:

- `observe()`
- `normalize()`
- `validate()`
- `generate_hypotheses()`
- `design_experiment()`
- `evaluate_evidence()`
- `calibrate_confidence()`
- `recommend()`
- `evaluate_outcome()`
- `learn()`
- `health_check()`

Every capability has:

- versioned input schema;
- versioned output schema;
- permission requirements;
- failure behavior;
- audit behavior;
- resource limits.

---

## 7. Required assets

Every pack includes:

- `PACK_CHARTER.md`
- `PACK_MANIFEST.yaml`
- `schemas/`
- `fixtures/`
- `tests/`
- `risk_policy.yaml`
- `freshness_policy.yaml`
- `calibration_policy.yaml`
- `autonomy_policy.yaml`
- `CHANGELOG.md`

Synthetic fixtures must allow sandbox testing without production access.

---

## 8. Missing-data policy

The default first response to missing material data is to request human input.

Each pack must additionally declare what happens when input is unavailable:

- block;
- reduce confidence;
- use a proxy;
- continue partially;
- return `UNKNOWN`.

No pack may silently fabricate or impute material data without labeling the method and uncertainty.

---

## 9. Risk and action contract

Risk classes:

- `LOW`
- `MODERATE`
- `HIGH`
- `CRITICAL`

Every executable action declares:

- maximum impact;
- reversibility;
- cost;
- affected people;
- required authorization;
- expiry;
- rollback;
- audit requirements;
- kill-switch behavior.

### Initial autonomy ceilings

- **Life:** recommend and prepare; automate only reversible preauthorized tasks.
- **Trading:** observe and recommend; paper execution may be authorized.
- **Betting:** observe and recommend; no real-money betting initially.
- **Business:** recommend and prepare; limited preauthorized administrative execution.

Autonomy can increase only through governed evidence.

---

## 10. Admission

A pack requires:

- high-value need;
- manual MVP demonstrating usefulness;
- observable data or defensible proxies;
- measurable outcomes;
- feedback cycle;
- risk controls;
- benefit above manual handling;
- Core reuse;
- sandbox operation;
- constitutional tests;
- owner approval.

---

## 11. Retirement

The principal retirement criterion is failure to provide sufficient value.

A pack must also be suspended immediately when it:

- violates the Constitution;
- creates uncontrolled risk;
- cannot protect data;
- becomes unauditable.

Retired packs preserve their data, evidence, outcomes, and learning in archive form.

Retirement does not erase knowledge.

---

## 12. Cross-Domain Coordinator

The Core includes a `Cross-Domain Coordinator`.

It does not independently decide. It:

- listens to relevant packs;
- detects conflicting recommendations;
- collects impacts and constraints;
- identifies local optimization risk;
- applies user-defined non-negotiable limits;
- produces global trade-offs;
- requests human resolution when values conflict.

Domain weights vary by decision and context.

Examples:

- Health can dominate during a medical emergency.
- Financial stability can gain weight during a liquidity crisis.
- A user may define absolute sleep, capital-risk, work-time, or betting limits.

Packs may challenge one another through published objections. They may not override one another directly.

---

## 13. Initial pack order

1. **Life Pack** — first integration and first vertical proof.
2. **Trading Pack** — second integration, reusing TradingMaxxxing evidence without replacing its existing research engine.
3. **Sports & Betting Pack** — third integration after cross-domain loop validation.

---

## 14. Pack certification tests

- `PACK_CHARTER_PRESENT`
- `PACK_SCHEMAS_VERSIONED`
- `PACK_FIXTURES_RUN_OFFLINE`
- `PACK_SANDBOX_ISOLATED`
- `PACK_MISSING_DATA_POLICY_EXPLICIT`
- `PACK_CALIBRATION_DOMAIN_SPECIFIC`
- `PACK_ACTION_RISK_DECLARED`
- `PACK_CANNOT_WRITE_OTHER_PACK`
- `PACK_NO_CORE_DUPLICATION`
- `PACK_CROSS_DOMAIN_IMPACT_PUBLISHED`

---
