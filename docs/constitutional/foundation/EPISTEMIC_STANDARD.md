# EPISTEMIC STANDARD

**Status:** Binding knowledge standard  
**Version:** 1.0  
**Parent authority:** Intelligence Engine Constitution v1.1

---

## 1. Purpose

This document defines how the Engine represents facts, uncertainty, evidence, causality, human values, experiments, and confidence.

Its goal is to ensure that the words “fact,” “evidence,” “confidence,” and “learning” mean the same thing across every Domain Pack.

---

## 2. Mandatory knowledge classes

Every knowledge object must declare one primary class:

- `OBSERVED_FACT`
- `DERIVED_FACT`
- `INFERENCE`
- `HYPOTHESIS`
- `EXPERIMENTAL_RESULT`
- `SUPPORTED_CONCLUSION`
- `OPERATIONAL_BELIEF`
- `HUMAN_VALUE`
- `UNKNOWN`

An assertion may have different classifications in different contexts. A population-level supported conclusion may remain a hypothesis for a specific person.

The context and scope are therefore mandatory fields.

---

## 3. Unknown states

`UNKNOWN` must include one reason:

- `MISSING_DATA`
- `CONTRADICTORY_DATA`
- `NOT_MEASURABLE_DIRECTLY`
- `INHERENT_RANDOMNESS`
- `METHOD_LIMITATION`
- `OUT_OF_DISTRIBUTION`
- `STALE_EVIDENCE`
- `INSUFFICIENT_POWER`

Every unknown response should include a learning plan when one is possible.

---

## 4. Confidence model

### 4.1 Required representation

Confidence must include:

- point estimate or probability;
- interval or uncertainty range;
- categorical label;
- historical calibration;
- domain randomness context;
- explanation.

Labels:

- `VERY_LOW`
- `LOW`
- `MODERATE`
- `HIGH`
- `VERY_HIGH`

### 4.2 Confidence decomposition

The Engine must distinguish:

- `data_confidence`
- `method_confidence`
- `conclusion_confidence`
- `recommendation_confidence`

A single final number may be shown for usability, but the components must remain auditable.

### 4.3 Domain calibration

An 80% or 99% estimate is meaningful only relative to a Domain Pack's calibration history and randomness model.

The Engine may display 99% when the evidence and calibrated model justify it. It must not artificially cap confidence, but must disclose:

- tail risk;
- events not represented in the model;
- calibration sample;
- expected error rate;
- randomness level;
- regime stability.

### 4.4 Confidence learning

The Engine must measure:

- overconfidence;
- underconfidence;
- calibration drift;
- accuracy by confidence bucket;
- calibration by context and regime.

---

## 5. Evidence hierarchy

Default hierarchy:

1. direct primary measurement;
2. audited primary dataset;
3. reproducible experiment;
4. independent official source;
5. reliable secondary source;
6. human observation;
7. model inference;
8. unverified data.

This order is a prior, not an automatic verdict. Relevance, independence, methodology, freshness, and context may alter the effective weight.

---

## 6. Human and manual data

### 6.1 Human observation

Human observations are valid evidence when marked with:

- observer;
- time;
- context;
- subjectivity level;
- expected bias;
- repeatability;
- verification status.

### 6.2 Manual user input

Trust policy depends on data type.

Examples:

- direct preference: authoritative as a current stated value;
- recalled historical event: accepted with memory uncertainty;
- measured weight copied from a scale: provisionally trusted;
- medical diagnosis or financial balance: requires source confirmation for high-impact use;
- emotional state: authoritative as a subjective report, not as an objective causal fact.

### 6.3 Feelings

For the Life Pack, feelings are real domain data.

They are:

- subjective;
- context-dependent;
- partly inferable;
- not perfectly repeatable;
- unsuitable for being dismissed as noise.

The Engine must distinguish reported feeling, inferred feeling, and behavioral proxy.

---

## 7. Freshness and temporal decay

Every Domain Pack must define freshness policies by object type.

Recent evidence weighs more only when the domain demonstrates temporal decay or regime change.

Examples:

- market price may become stale in seconds;
- recent football form may decay across weeks or months;
- a long-term personal value may remain relevant for years;
- an old experimental result may remain valid if the mechanism and environment remain stable.

Freshness is not recency bias. The Engine must justify why time changes evidential weight.

---

## 8. Source independence

The Engine must model source lineage and dependency.

Evidence copied from a common source must not be counted as independent confirmation.

Required lineage fields include:

- source ID;
- parent source where known;
- acquisition method;
- transformation chain;
- dataset overlap;
- temporal overlap;
- suspected common dependency.

---

## 9. Causality standard

### 9.1 Levels

- `CORRELATION`
- `PLAUSIBLE_CAUSAL_LINK`
- `CAUSAL_EVIDENCE`
- `REPLICATED_CAUSAL_EVIDENCE`

### 9.2 Requirements

Correlation alone does not justify causal language.

Causal claims require an appropriate combination of:

- controlled experiment;
- quasi-experimental design;
- defensible mechanism;
- confounder controls;
- temporal ordering;
- robustness;
- replication.

### 9.3 Useful correlations

The Engine may recommend action from a useful correlation when:

- causal uncertainty is explicit;
- downside is controlled;
- reversibility is considered;
- the correlation is stable enough for the purpose;
- the recommendation does not claim causality.

---

## 10. Experiment standard

### 10.1 Pre-registration

A material experiment must define before execution:

- hypothesis;
- outcome;
- metrics;
- population or scope;
- duration;
- sample policy;
- comparison baseline;
- success criteria;
- abandonment criteria;
- risk limits;
- analysis plan.

### 10.2 Post-hoc hypotheses

A hypothesis generated after observing an outcome is marked `POST_HOC`.

It requires new validation data before promotion.

### 10.3 Multiple testing and data mining

The Engine must account for:

- multiple comparisons;
- researcher degrees of freedom;
- repeated use of the same dataset;
- selection bias;
- p-hacking equivalents;
- feature and strategy search;
- survivor bias.

### 10.4 In-sample evidence

Each Domain Pack defines the exact rule, but:

- in-sample evidence must always be labeled;
- predictive financial or betting claims cannot be considered finally validated from in-sample evidence alone;
- low-risk descriptive or qualitative domains may use in-sample evidence operationally only with explicit limitations;
- any generalization beyond the observed sample requires new validation.

### 10.5 Early stopping

An experiment may stop early for:

- harm;
- futility;
- exceptional evidence under a predefined stopping rule;
- contamination;
- excessive cost;
- invalidated assumptions.

Stopping and its reason must be recorded.

---

## 11. Human values

### 11.1 Sources of values

Values may come from:

- stable configuration;
- decision-specific questions;
- confirmed historical learning;
- current context.

### 11.2 Inferred values

The Engine may always suggest inferred values from behavior, but they do not become authoritative until confirmed.

### 11.3 Value contradiction

The Engine must distinguish:

- stated values;
- revealed values from behavior;
- values inferred as potentially beneficial.

Contradictions must be shown prospectively and neutrally so the user can learn. The Engine must not secretly rewrite a person's values based on past behavior.

---

## 12. Required epistemic object fields

Every material knowledge object includes:

- `id`
- `knowledge_class`
- `scope`
- `domain_pack`
- `subject`
- `statement`
- `source_ids`
- `context`
- `observed_at`
- `recorded_at`
- `freshness_state`
- `confidence_components`
- `causality_level`
- `limitations`
- `contradictions`
- `version`
- `audit_id`

---

## 13. Epistemic tests

- `INFERENCE_NEVER_SERIALIZED_AS_FACT`
- `UNKNOWN_HAS_REASON`
- `UNKNOWN_HAS_LEARNING_PLAN_WHEN_POSSIBLE`
- `CONFIDENCE_COMPONENTS_PRESENT`
- `DOMAIN_CALIBRATION_REQUIRED`
- `SOURCE_DEPENDENCY_DEDUPED`
- `POST_HOC_REQUIRES_NEW_VALIDATION`
- `CAUSAL_LANGUAGE_REQUIRES_CAUSAL_LEVEL`
- `FEELING_REPORTED_VS_INFERRED_SEPARATED`
- `STALE_POLICY_DECLARED_BY_PACK`

---
