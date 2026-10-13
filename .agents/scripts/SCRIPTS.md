#  Scripts & Automation Index

This directory contains global utilities and automation scripts for the **Portable Brainvibing** infrastructure.

## Modular CLI: `orion.py`

This directory uses a **Modular CLI** architecture. Instead of calling individual scripts, use the `orion.py` entrypoint.

| Command | Purpose | Target Script |
| :--- | :--- | :--- |
| `python .agents/scripts/orion.py brain sync` | Local hybrid RAG (FTS5 + vectors + 1-hop graph). | `commands/brain.py` |
| `python .agents/scripts/orion.py verify` | Scans for broken links/headers (Mechanical Audit). | `commands/verify_agents.py` |
| `python .agents/scripts/orion.py context-lint` | Validates `context/` naming against registry. | `commands/context_naming_lint.py` |
| `python .agents/scripts/orion.py deploy` | Physically deploys/syncs Foundation to a local project. | `commands/foundation.py` |
| `python .agents/scripts/orion.py push-upstream` | Guides manual curation of local learnings to Foundation. | `commands/foundation.py` |
| `python .agents/scripts/orion.py budget` | Tracks budget, tiers, and Small Model Superiority telemetry. | `commands/track_budget.py` |
| `python .agents/scripts/orion.py scan tokens` | Ghost Token Auditor (detects memory bloat). | `core/scanner.py` |
| `python .agents/scripts/orion.py scan map` | Structural Code Mapper (generates lightweight skeleton). | `core/scanner.py` |
| `python .agents/scripts/orion.py scan targets` | Identifies targets for the Offensive Audit protocol. | `core/scanner.py` |
| `python .agents/scripts/orion.py scan security` | Scans rules and code for security risks. | `core/scanner.py` |
| `python .agents/scripts/orion.py preflight` | Pre-flight diagnostic (Self-Healing Routing). | `commands/preflight_check.py` |
| `python .agents/scripts/orion.py compress` | Compresses episodic memory into Lessword format. | `commands/compress_memory.py` |
| `python .agents/scripts/orion.py orion_ops init` | Initializes the `.orion/` infrastructure. | `commands/orion_ops.py` |
| `python .agents/scripts/orion.py orion_ops ingest`| Ingests rules and configs into the `.orion/` graph. | `commands/orion_ops.py` |
| `python .agents/scripts/orion.py linkify` | Auto-injects wikilinks across context and agent files. | `commands/linkify.py` |
| `python .agents/scripts/orion.py compile` | Compiles Markdown rules into dense JSON matrices. | `commands/compile_rules.py` |
| `python .agents/scripts/orion.py matrix` | Queries compiled JSON matrices in `.orion/matrix`. | `commands/matrix_query.py` |
| `python .agents/scripts/orion.py adversarial` | Enforces red-green test-driven development. | `commands/adversarial.py` |
| `python .agents/scripts/orion.py raw_ingest` | Ingests unstructured files in `context/raw/` to wiki. | `commands/raw_ingest.py` |
| `python .agents/scripts/orion.py amnesia` | Rule eviction mechanism (usage-based). | `commands/rule_eviction.py` |
| `python .agents/scripts/orion.py rtk` | RTK Proxy. | `core/rtk_proxy.py` |
| `python .agents/scripts/orion.py fsm` | Crash-proof formal state machine execution tracker. | `commands/state_machine.py` |
| `python .agents/scripts/orion.py contradict` | Detects and resolves colliding triplet predicates. | `commands/contradict.py` |
| `python .agents/scripts/orion.py consolidate` | Activity-based temporal pulse knowledge synthesis. | `commands/consolidate.py` |
| `python .agents/scripts/orion.py eval` | CI/CD gatekeeper for UI aesthetics and tokens. | `evals/audit_aesthetics.py` |

## Organization Policy

1. **Global Entrypoint**: `orion.py` is the only script called directly.
2. **Command Modules**: Placed in `commands/`.
3. **Core Utilities**: Placed in `core/`.
4. **Output Files**: Scripts should NEVER write persistent logs or reports to the root. Use a `logs/` folder or system-specific temp directories.
