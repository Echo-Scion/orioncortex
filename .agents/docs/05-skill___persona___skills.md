# VOLUME V: SKILL / PERSONA (`skills/`) — 21 Domain Pillars

---

## Chapter 10: Skill Concept
Each skill is a modular 3-tier specialization worn by the AI:
- **Tier 1 (Frontmatter)**: Discovery metadata (<100 tokens).
- **Tier 2 (SKILL.md Body)**: Actionable runbook (<500 lines).
- **Tier 3 (references/ & scripts/)**: Deep domain knowledge and specialized operational workflows loaded on demand.

### 10.1. `ai-engineer`
**Domain:** Mitigating the probabilistic nature of LLMs.
**Content:** Assertion matrix, Confidence Gates, anti-hallucination.

### 10.2. `api-contract`
**Domain:** Client/server interface contracts.
**Content:** OpenAPI specifications, Zod validation, API safety patterns.
**Reference:** `.agents/skills/api-contract/references/api_safety_patterns.md`.

### 10.3. `app-lifecycle`
**Domain:** Master Full Lifecycle Pipeline & State Machine.
**Content:** Orchestrates phase transitions across the complete project lifecycle.
**Consolidated References:**
- `project-init.md`: Greenfield Scaffolding Engine.
- `project-migrate.md`: Brownfield & Legacy Onboarding.
- `app-builder.md`: Surgical Feature Construction.
- `feature-sunset.md`: Phased Deprecation & Sunsetting Protocol.

### 10.4. `brain-graph`
**Domain:** Operating `orion.db` and local RAG.
**Content:** FTS5 querying, triplet injection, SQLite maintenance.
**Consolidated Reference:**
- `knowledge-extraction.md`: Semantic Graph Triplet Extraction.

### 10.5. `lessword`
**Domain:** Ultra-terse communication compression.
**Content:** 6 intensity levels. Supports `wenyan` (classical Chinese variant).
**Consolidated Reference:**
- `lessword-compress.md`: Token reduction for memory and task files.

### 10.6. `code-review`
**Domain:** Offensive Security Audit & PR Review.
**Content:** OWASP security checks, algorithmic mutation testing, temporal state simulation, and Lessword review formatting.

### 10.7. `cost-optimizer`
**Domain:** Token and cloud budget management.
**Content:** Routing cheap models for simple tasks, expensive models for complex tasks.

### 10.8. `data-logic`
**Domain:** Data immutability.
**Content:** Forbids global state, Redux/Zustand patterns, pure functions, immutable DTOs.

### 10.9. `frontend-experience`
**Domain:** UI/UX debugging & frontend performance.
**Content:** Fixing excessive re-renders, DOM infinite loops, React/Flutter state synchronization.
**Reference:** `.agents/skills/frontend-experience/references/ux-designer.md`.

### 10.10. `integrity-sentinel`
**Domain:** Quality Enforcement Hub, Red Team & Automated QA.
**Content:** Architecture audit, bloat audit, duplicate audit, fail-fast audit, logic audit, performance audit, retry audit, load testing, pre-completion verification gate.
**References:** Comprehensive suite in `references/` including `audit-ledger.md` (multi-session audit state).

### 10.11. `meta-agent-admin`
**Domain:** Architect of the `.agents` ecosystem.
**Content:** Ecosystem evolution, rule creation, routing integrity, and foundation engine self-audit.
**References:** `agent-architect.md`, `agent-evolution.md`, `context-manager.md`, `knowledge.md`, `loop_design_patterns.md`, `meta-agent-audit.md`, `system-admin.md`, `tech-writer.md`, `mcp-builder.md`, `skills-catalog.md`, and `knowledge-sync.md`.

### 10.12. `palette`
**Domain:** Micro-aesthetics & accessibility.
**Content:** CSS tokens, smooth animations, ARIA labels, glassmorphism, color harmony, keyboard navigation.

### 10.13. `project-architect`
**Domain:** High-scale PRD & Blueprints, Master backend architect.
**Content:** Translating user ideas into technical documents, Node.js memory management, connection pooling, SQL optimization, database indexing.
**References:** Deep suite in `references/` including `architectural_standards.md`, `backend-architect.md`, `enterprise_patterns.md`.

### 10.14. `project-operator`
**Domain:** DevOps & resilience.
**Content:** Dockerfiles, CI/CD pipelines, Nginx, chaos engineering, pre-production deployment readiness (`prod-deploy.md`).
**References:** `chaos-engineer.md`, `release-manager.md`, `prod-deploy.md`.

### 10.15. `saas-strategist`
**Domain:** SaaS business strategy.
**Content:** Viability analysis, monetization, growth, viral content.
**References:** `saas-growth.md`, `saas-viability.md`, `technical_content.md`, `viral_growth.md`.

### 10.16. `self-evolve`
**Domain:** Deterministic Reflection & Evolution Loop.
**Content:** 4 phases: Error extraction → Memory write (`LEARNINGS.md`) → Darwinian A/B evaluation → Recurring pattern synthesis into permanent skills or rules.
**Consolidated Reference:**
- `temporal-pulse.md`: Activity-based cadence synthesis (Session, Milestone, Epoch).

### 10.17. `session-offload`
**Domain:** Clean Shutdown & Context Eviction.
**Content:** Scratchpad eviction, gated auto-commit, episodic observation logging, memory compaction, and handoff state generation (`.orion/working/handoff.md`).
**Consolidated Reference:**
- `auto-context.md`: Organic Business Rule Extraction.

### 10.18. `strict-tdd`
**Domain:** Strict Test-Driven Development Loop.
**Content:** RED-GREEN-REFACTOR cycle with mandatory mechanical rollback (`git stash`) if implementation code is written before a verified failing test.

### 10.19. `systematic-debugging`
**Domain:** 4-Phase Scientific Root-Cause Discipline.
**Content:** Phase 1 (Investigation) → Phase 2 (Pattern analysis) → Phase 3 (Hypothesis testing) → Phase 4 (Surgical fix with 3-attempt circuit breaker).

### 10.20. `ui-finish`
**Domain:** Premium UI final polish.
**Content:** Empty states, loading spinners, error boundaries, visual craft and contrast audits.
**Reference:** `.agents/skills/ui-finish/references/visual_engineering.md`.

### 10.21. `worker-delegate`
**Domain:** Sub-agent orchestration and task decomposition.
**Content:** Splitting heavy workflows into narrow, isolated tasks; spawning dedicated sub-agent workers; storing temporary state in `.agents/working/delegations/`.

---

