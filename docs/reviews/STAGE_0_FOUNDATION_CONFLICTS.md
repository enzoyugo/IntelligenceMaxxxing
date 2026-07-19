# STAGE 0 — FOUNDATION CONFLICTS

**Scope:** contradictions found while reading the constitutional foundation before implementing Stage 0.
**Authority order applied:** Constitution → Constitutional Changes → Governance → Epistemic Standard → Domain Pack Standard → Service Contract → Technical Architecture.

---

## Verdict

**No genuine constitutional contradiction was found.** The seven foundational
documents are mutually consistent. No document was modified. The divergences
below are structural/administrative and were resolved without touching any
constitutional text.

---

## D-1. Document location vs. expected flat layout

- **Observed:** the Stage 0 instructions list the seven documents as if they
  lived directly under `docs/constitutional/`. In the repository they live in
  `docs/constitutional/foundation/` and `docs/constitutional/architecture/`.
- **Resolution:** treated as an organizational detail, not a conflict. The
  SHA-256 manifest covers the whole `docs/constitutional/` tree recursively.
  No file was moved (moving would alter the frozen foundation).

## D-2. Repository layout: TECHNICAL_ARCHITECTURE §4 vs. Stage 0 target structure

- **Observed:** TECHNICAL_ARCHITECTURE.md §4 sketches top-level modules such as
  `observations/`, `beliefs/`, `audit/` directly under `intelligence_maxxxing/`,
  while the Stage 0 brief prescribes a layered layout (`domain/`, `application/`,
  `infrastructure/`, `api/`, `contracts/`).
- **Analysis:** TECHNICAL_ARCHITECTURE is the lowest-authority document and its
  own §4 note says module rules are what matter ("Module rules are enforced with
  import-boundary tests"). The layered layout implements the same modular
  monolith with stricter, testable boundaries; every module named in §4 exists
  as a subpackage of a layer (e.g. `domain/observations`, `domain/beliefs`).
- **Resolution:** layered structure adopted; boundaries enforced by
  import-linter and `tests/constitutional/test_import_boundaries.py`. Not a
  constitutional conflict.

## D-3. `FOUNDATION_DECISIONS_SOURCE.txt` inside the frozen tree

- **Observed:** the source Q&A transcript lives inside `docs/constitutional/`
  although it is a working record, not a numbered authority document.
- **Resolution:** it documents the Constitutional Owner's decisions, so it was
  frozen and hashed with the rest. It is treated as historical evidence, below
  every numbered document in authority.

---

No entry above required applying a higher-authority override, and none
resulted in a modification of any constitutional document.
