---
description: Master index for all foundation rules.
activation: always on
---

# 📚 Rules Index

This directory contains the core behavioral and operational constraints for the `_foundation` ecosystem. These files enforce how the AI plans, writes code, manages state, and performs tests.

## Core Rules

| File | Purpose |
| :--- | :--- |
| `core-guardrails.md` | **(START HERE)** The master AI behavioral protocol and operation constraints. |
| `.agents/skills/ai-engineer/SKILL.md` | Concrete engineering algorithms to mitigate fundamental AI traits (Probabilistic nature, GIGO, Black Box). |
| `tier-execution-protocol.md` | Execution depth per tier (Budget/Standard/Premium) and reasoning standards. |
| `security-guardrails.md` | Absolute security constraints, offensive zero-trust audits, and Red Team exploit generation. |
| `.agents/skills/ui-finish/SKILL.md` | Frontend UI/UX aesthetics, 20+ design archetypes, and restrained ergonomics. |
| `.agents/skills/api-contract/SKILL.md` | Strict backend data contracts (Zod, OpenAPI). |
| `development-operations.md` | Git workflows, PR reviews, Auto-Harness validation pipelines. |
| `prompting-patterns.md` | Advanced prompting patterns for sub-agent orchestration and determinism. |
| `antigravity-rtk-rules.md` | Rules for interacting with the RTK context proxy. |
| `performance-optimization.md` | Decision trees for performance optimization, token usage, and Bolt-level speed enforcement. |
| `.agents/skills/app-lifecycle/SKILL.md` | Crash-proof formal state machine protocol for multi-step tasks. |
| `contradiction-protocol.md` | Protocol for resolving colliding predicates and rule conflicts. |
| `memory-hygiene.md` | Rules for episodic memory compression and GraphRAG garbage collection. |
| `fsm-protocol.md` | Formal State Machine execution tracking and crash recovery protocol. |
| `prose-authenticity.md` | 54-pattern tell taxonomy, binary contrast reversals, and anti-slop documentation standards. |
| `four-pillars-architecture.md` | Four (4) Permanently Anchored Pillars and hierarchical graceful degradation protocol. |

---
*Policy: If a new rule is added, it MUST be indexed here and MUST include a frontmatter with `description` and `activation` tags.*
