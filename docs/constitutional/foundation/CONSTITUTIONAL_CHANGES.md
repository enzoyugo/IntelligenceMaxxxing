# CONSTITUTIONAL CHANGES

**Document authority:** Constitutional amendment ledger  
**Current Constitution version:** 1.1  
**Rule:** Append-only. Historical entries must never be rewritten or deleted.

---

## Amendment 001 — Engine Independence and Application Boundary

**Status:** APPROVED  
**Effective date:** 2026-07-19  
**Approved by:** Constitutional Owner  
**Previous version:** 1.0  
**New version:** 1.1

### Problem

The original Constitution described a universal Core Engine and Domain Packs, but it did not explicitly protect the Engine's operational independence from TradingMaxxxing, LifeMaxxxing, the betting bot, or future applications.

Without an explicit boundary, the project could gradually become a shared code folder, a UI-specific backend, or a collection of direct database integrations. That would compromise domain independence, auditability, security, versioning, and long-term reuse.

### Decision

The Engine is constitutionally defined as an independent backend service.

Applications:

- remain separate products;
- preserve their own UI and local operating state;
- communicate through public versioned contracts;
- cannot import internal Core modules;
- cannot access Engine databases directly;
- cannot rewrite conclusions or beliefs;
- may only submit observations, evidence, decisions, outcomes, and governed requests.

### Constitutional modifications

- Added **Article 4-A — Independencia del Engine como servicio**.
- Added **Article 43-A — Frontera con las aplicaciones**.
- Added **Law 21 — Engine independence from applications**.
- Updated the working project name to **IntelligenceMaxxxing / Intelligence Engine**.

### Risks considered

- Additional API and synchronization complexity.
- Need for authentication, compatibility testing, idempotency, and offline queues.
- Higher initial infrastructure cost than a single embedded backend.

### Expected benefits

- True domain independence.
- Reusable intelligence across all applications.
- Better privacy and permission boundaries.
- Independent deployment and scaling.
- Clear ownership of data and conclusions.
- Ability to replace any frontend without rebuilding the Engine.
- Lower risk of duplicating research and learning logic.

### Rollback

Not permitted as a standard rollback. Removing this boundary requires explicit project refoundation because Engine independence is a protected constitutional clause.

---
