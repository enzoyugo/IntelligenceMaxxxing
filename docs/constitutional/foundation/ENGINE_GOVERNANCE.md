# ENGINE GOVERNANCE

**Status:** Binding governance standard  
**Version:** 1.0  
**Parent authority:** Intelligence Engine Constitution v1.1

---

## 1. Purpose

This document defines how IntelligenceMaxxxing changes, promotes methods, responds to incidents, audits itself, and preserves constitutional control.

Governance exists to prevent the Engine from improving only in appearance, promoting unvalidated methods, hiding failures, or allowing applications and AI agents to acquire authority they do not possess.

---

## 2. Initial authority model

### 2.1 Constitutional Owner

The initial Constitutional Owner is the project creator.

The Constitutional Owner has exclusive authority to:

- approve constitutional amendments;
- approve project refoundation;
- appoint or remove governance roles;
- approve critical production promotions;
- approve changes to protected metrics;
- authorize new Domain Packs;
- authorize higher autonomy levels.

### 2.2 Defined roles

Even when one person initially occupies every role, the Engine recognizes:

- `CONSTITUTIONAL_OWNER`
- `ENGINE_MAINTAINER`
- `DOMAIN_PACK_OWNER`
- `RESEARCH_REVIEWER`
- `PRODUCTION_APPROVER`
- `DATA_OWNER`
- `APPLICATION_OWNER`

### 2.3 Future separation of duties

As the project grows, a critical change must not be proposed, validated, and approved by the same person.

At minimum, future critical promotions require:

1. one proposer;
2. one independent reviewer;
3. one production approver;
4. Constitutional Owner approval when protected principles or metrics are affected.

### 2.4 AI authority

AI agents may:

- propose changes;
- generate hypotheses;
- execute tests;
- prepare reports;
- detect degradation;
- recommend promotion, rollback, or suspension.

AI agents may never:

- amend the Constitution;
- grant themselves permissions;
- approve production changes;
- redefine protected metrics;
- override a valid human decision;
- promote a method directly to `ACTIVE`.

---

## 3. Constitutional change management

### 3.1 Changes requiring amendment

A constitutional amendment is required to change:

- the authority hierarchy;
- human control requirements;
- data ownership or privacy rights;
- traceability requirements;
- protected prohibitions;
- decision/outcome separation;
- Engine independence from applications;
- the right to audit;
- the obligation to learn;
- constitutional autonomy limits.

### 3.2 Protected clauses

The following may only be changed through explicit project refoundation:

- evidence must not be invented;
- evidence and decisions must remain traceable;
- humans retain final authority where constitutionally required;
- personal data belongs to its owner;
- decision quality and outcome remain distinct;
- the Engine must learn from outcomes;
- historical auditability is preserved;
- the Engine remains independent from applications.

### 3.3 Amendment record

Every amendment must be appended to `CONSTITUTIONAL_CHANGES.md` and include:

- affected articles;
- problem statement;
- supporting evidence;
- risks;
- cross-domain impact;
- previous version;
- new version;
- explicit approval;
- effective date;
- rollback or refoundation implications.

### 3.4 Emergency changes

Emergency governance may suspend, isolate, block, or degrade capabilities before normal review is complete.

Emergency governance may never:

- promote a new capability;
- increase autonomy;
- weaken access control;
- remove audit history;
- change a protected metric.

Every emergency action requires a postmortem.

---

## 4. Universal method lifecycle

All governed methods use the following states:

1. `IDEA`
2. `EXPERIMENTAL`
3. `SANDBOX`
4. `SHADOW`
5. `CANDIDATE`
6. `APPROVED`
7. `ACTIVE`
8. `DEGRADED`
9. `SUSPENDED`
10. `RETIRED`

No state may be skipped without a documented emergency exception that can only reduce capability, never increase it.

---

## 5. Promotion policy

### 5.1 Minimum promotion evidence

A method moving from `SHADOW` toward `ACTIVE` must demonstrate:

- material improvement against a declared baseline;
- temporal or contextual stability appropriate to its domain;
- absence of leakage;
- reproducibility;
- calibrated confidence;
- passing constitutional tests;
- controlled risk;
- human approval.

### 5.2 No hidden regressions

Performance improvement is insufficient when the candidate materially worsens:

- explainability;
- stability;
- risk;
- latency;
- privacy;
- maintainability;
- resource usage;
- cross-domain impact.

Any accepted regression must be explicit, quantified, and approved.

### 5.3 Threshold ownership

Promotion thresholds are jointly determined by:

- constitutional constraints;
- this Governance standard;
- Domain Pack rules;
- user risk limits;
- evidence from the candidate experiment.

A Domain Pack can be stricter than Governance, never weaker.

### 5.4 Champion/challenger

After promotion, the previous method remains available as a baseline or fallback for a defined observation period.

The promoted method operates under champion/challenger monitoring until the Domain Pack's stabilization threshold is met.

### 5.5 Rollback

- Clear threshold breaches trigger automatic rollback.
- Ambiguous degradations trigger human review and may trigger temporary return to `SHADOW`.
- Rollback must preserve all evidence generated by the failed promotion.

---

## 6. Degradation and incident response

### 6.1 Severity levels

- `SEV-0`: critical harm, loss of control, or unauthorized execution.
- `SEV-1`: materially incorrect decision or major data/security failure.
- `SEV-2`: significant degradation with contained impact.
- `SEV-3`: limited error without material impact.
- `SEV-4`: informational anomaly or near miss.

### 6.2 Automatic kill-switch conditions

A kill switch must activate for:

- invented or fabricated evidence;
- confirmed data contamination affecting conclusions;
- execution beyond authorization;
- severe loss of calibration;
- silent metric changes;
- inability to reconstruct material recommendations;
- cross-tenant or cross-domain privacy breach;
- uncontrolled duplicate execution;
- constitutional test failure in an active method.

### 6.3 Degraded method behavior

A degraded method must:

1. stop autonomous execution;
2. return to `SHADOW`;
3. preserve observation where safe;
4. be investigated;
5. expose its health status to applications;
6. reduce or withdraw its recommendations.

### 6.4 Partial operation

The Engine may continue operating when a module is degraded if:

- the module is isolated;
- affected capabilities are explicit;
- health status is included in responses;
- unrelated modules remain trustworthy;
- critical execution paths are blocked.

### 6.5 Postmortems

Every `SEV-0`, `SEV-1`, and material `SEV-2` requires an immutable postmortem containing:

- timeline;
- impact;
- detection;
- root cause;
- contributing factors;
- missed controls;
- corrective actions;
- prevention tests;
- owners and deadlines.

---

## 7. Audit and reconstruction

### 7.1 Retention

Knowledge objects, recommendations, decisions, evidence, and outcomes are retained indefinitely unless privacy law or an authorized deletion process requires otherwise.

### 7.2 Recommendation audit bundle

Every material recommendation must have a reconstructable audit bundle containing:

- recommendation ID;
- model and provider version;
- Domain Pack version;
- Engine version;
- data identifiers and freshness;
- experiment and evidence IDs;
- parameters;
- rules;
- human values used;
- context;
- confidence decomposition;
- timestamp;
- health state;
- authorization state.

The audit bundle is a structured record, not merely a narrative document.

### 7.3 Engine self-evaluation

The Engine periodically reports:

- calibration;
- good decisions with bad outcomes;
- bad decisions with good outcomes;
- overconfidence and underconfidence;
- degraded beliefs;
- missed opportunities;
- human disagreements;
- cross-domain conflicts;
- learning produced;
- repeated errors.

### 7.4 Governance review cadence

A formal governance review occurs every six months and after:

- any constitutional amendment;
- any `SEV-0`;
- a major autonomy increase;
- admission of a critical-risk Domain Pack.

---

## 8. Protected metrics

Each Domain Pack must declare protected metrics.

A protected metric change requires:

- explicit versioning;
- baseline comparison;
- historical bridge where possible;
- reason and evidence;
- approval;
- entry in the relevant change ledger.

A metric may not be redefined retroactively to improve reported performance.

---

## 9. Governance tests

Minimum governance tests include:

- `NO_AI_FINAL_APPROVAL`
- `NO_STATE_SKIP_TO_ACTIVE`
- `PROMOTION_REQUIRES_BASELINE`
- `PROMOTION_REQUIRES_CONSTITUTIONAL_TESTS`
- `ROLLBACK_AVAILABLE`
- `KILL_SWITCH_EXECUTION_AUTHORITY`
- `AUDIT_BUNDLE_RECONSTRUCTABLE`
- `NO_SILENT_METRIC_CHANGE`
- `DEGRADED_RETURNS_TO_SHADOW`
- `APPLICATION_CANNOT_BYPASS_PUBLIC_CONTRACT`

---
