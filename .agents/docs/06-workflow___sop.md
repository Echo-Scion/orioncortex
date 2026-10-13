# VOLUME VI: WORKFLOW / SOP — 18 Standard Operating Procedures

---

## Chapter 11: Complete List of Modular Workflows

The `.agents` ecosystem organizes operational procedures into focused, single-responsibility workflows adhering to the 3-tier progressive context disclosure standard (<7KB per workflow):

### 11.1. `app-lifecycle.md` (`/app-lifecycle`, `/full-lifecycle`)
**Master Full Lifecycle Pipeline & State Machine.** Evaluates project maturity and orchestrates phase transitions: Phase 0 (State Init) → Phase 1 (Strategy) → Phase 2 (Architecture) → Phase 3 (TDD) → Phase 4 (UI Polish) → Phase 5 (Security) → Phase 6 (Offload).

### 11.2. `project-init.md` (`/project-init`)
**Greenfield Scaffolding Engine.** Enforces strict 3-question requirements intake, builds the 4 lean pillars in `context/` (`BLUEPRINT.md`, `ROADMAP.md`, `STYLE_GUIDE.md`, `ARCHITECTURE.md`), and automatically synthesizes `DESIGN.md` tokens.

### 11.3. `app-builder.md` (`/app-builder`)
**Surgical Feature Construction.** End-to-end feature creation cycle: Shape Spec → Bento-Box Aesthetic Design → Immutable Domain Models → Adversarial Twin Protocol → Thompson Sampling verification loop (100% test pass rate gate).

### 11.4. `feature-sunset.md` (`/feature-sunset`)
**Phased Deprecation & Sunsetting Protocol.** 4-phase transition: Replacement construction → Telemetry notice → Dual-write expand-contract transition → Compulsory dead code purge.

### 11.5. `audit-and-test.md` (`/audit-and-test`)
**Unified Quality Enforcement & Audit Hub.** Orchestrator routing to Strict TDD, Systematic Debugging, and Code Review. Embeds the Pre-Completion Verification Gate (The Iron Evidence Law: fresh execution proof required before claiming success).

### 11.6. `strict-tdd.md` (`/strict-tdd`)
**Strict Test-Driven Development Loop.** RED-GREEN-REFACTOR cycle with mandatory mechanical rollback (`git stash`) if implementation code is written before a verified failing test (`Exit Code > 0`). Automatically bridges with `AUDIT_STATE.md` and `00-ledger.md`.

### 11.7. `systematic-debugging.md` (`/systematic-debugging`)
**4-Phase Scientific Root-Cause Discipline.** Phase 1 (Root cause investigation) → Phase 2 (Differential pattern analysis) → Phase 3 (Single hypothesis testing) → Phase 4 (Surgical fix with 3-attempt circuit breaker).

### 11.8. `code-review.md` (`/code-review`)
**Offensive Security Audit & PR Review.** OWASP security checks, algorithmic mutation testing, temporal state simulation, and Lessword review formatting (`🔴 bug:`, `🟡 risk:`, `🔵 nit:`, `❓ q:`).

### 11.9. `audit-ledger.md` (`/audit-ledger`)
**Formal Audit Ledger & State Protocol.** Maintains persistent finding tracking across long-running or multi-session codebase audits.

### 11.10. `auto-context.md` (`/auto-context`)
**Organic Business Rule Extraction.** Captures conversational clarifications and user course-corrections, formalizing them into structured `context/` domain files before session memory eviction.

### 11.11. `knowledge-extraction.md` (`/knowledge-extraction`)
**Semantic Graph Extraction.** Guides agents in analyzing code syntax, isolating 3-5 semantic triplets `(Subject, Predicate, Object)`, and injecting them into `orion.db`.

### 11.12. `knowledge-sync.md` (`/knowledge-sync`)
**Foundation Knowledge Synchronization.** Internal DevOps procedure for version bumping, knowledge graph consistency checks, and git release commits.

### 11.13. `orion-ops.md` (`/orion-ops`)
**Brain Graph Operating Procedures.** Standard operations for initializing `.orion/`, FTS5 database re-indexing, graph querying, and SQLite schema repairs.

### 11.14. `prod-deploy.md` (`/prod-deploy`)
**Pre-Production Deployment Readiness.** Release checklist covering environment hermeticity, secrets verification, build minification, and rollback readiness.

### 11.15. `project-migrate.md` (`/project-migrate`)
**Brownfield & Legacy Onboarding.** Scaffolds the `.agents` infrastructure into existing codebases without mutating running application architecture or breaking existing builds.

### 11.16. `self-evolve.md` (`/self-evolve`)
**Deterministic Reflection & Evolution Loop.** 4 phases: Error extraction → Memory write (`LEARNINGS.md`) → Darwinian A/B evaluation → Recurring pattern synthesis into permanent skills or rules.

### 11.17. `session-offload.md` (`/session-offload`)
**Clean Shutdown & Context Eviction.** Scratchpad eviction, gated auto-commit, episodic observation logging (`[decision]`, `[bugfix]`, `[feature]`), memory compaction, and handoff state generation (`.orion/working/handoff.md`).

### 11.18. `temporal-pulse.md` (`/temporal-pulse`)
**Activity-Based Temporal Evolution.** 3 non-calendar cadences: Session Pulse (per offload) → Milestone Synthesis (every 5 sessions) → Epoch Consolidation (every 4 milestones).
