# VOLUME VII: PYTHON SCRIPTS (`scripts/`) — Execution Engine

---

## Chapter 12: Script Architecture

### 12.1. Entry Point: `orion.py`
The only script called directly. All commands are routed through this modular CLI.

### 12.2. Complete Command Table

| Command | Target Script | Function |
|:--|:--|:--|
| `brain` | `commands/brain.py` | Local RAG: FTS5 BM25 + cosine similarity + 1-hop SQLite graph traversal |
| `verify` | `commands/verify_agents.py` | Markdown compiler & integrity gatekeeper — scans all links, detects phantom references |
| `context-lint` | `commands/context_naming_lint.py` | Validates context file naming against standard SaaS registry |
| `deploy` | `commands/foundation.py` | Deploys/scaffolds Foundation to a target project with placeholder resolution |
| `push-upstream` | `commands/foundation.py` | Syncs project evolutions back to master Foundation |
| `budget` | `commands/track_budget.py` | Tracks budgets, model tiers, and Small Model Superiority telemetry |
| `scan tokens` | `core/scanner.py` | Ghost Token Auditor — detects memory bloat |
| `scan map` | `core/scanner.py` | Structural Code Mapper — creates lightweight skeletons |
| `scan targets` | `core/scanner.py` | Identifies targets for Offensive Audit |
| `preflight` | `commands/preflight_check.py` | Pre-flight diagnostics and environment checks |
| `compress` | `commands/compress_memory.py` | Compresses episodic memory files to Lessword format |
| `orion_ops init` | `commands/orion_ops.py` | Initializes the `.orion/` SQLite schema and directories |
| `orion_ops ingest` | `commands/orion_ops.py` | Ingests rules, context, and semantic triplets into the graph |
| `linkify` | `commands/linkify.py` | Auto-injects wikilinks across context and agent files |
| `compile` | `commands/compile_rules.py` | Compiles human-readable Markdown rules into dense JSON matrices |
| `matrix` | `commands/matrix_query.py` | Fast keyword queries against compiled JSON rule matrices |
| `adversarial` | `commands/adversarial.py` | Enforces red-green TDD execution (run failing test before implementation) |
| `raw_ingest` | `commands/raw_ingest.py` | Ingests unstructured files in `context/raw/` into structured markdown in `context/wiki/` |
| `amnesia` | `commands/rule_eviction.py` | Usage-based stale asset eviction (garbage collection) |
| `rtk` | `core/rtk_proxy.py` | RTK terminal token-reduction proxy |
| `fsm` | `commands/state_machine.py` | Crash-proof formal state machine execution tracker |
| `contradict` | `commands/contradict.py` | Detects and resolves colliding triplet predicates in the graph |
| `consolidate` | `commands/consolidate.py` | Temporal pulse: session, milestone, epoch episodic distillation |
| `eval` | `evals/audit_aesthetics.py` | Scans UI code for design tokens, raw colors, and interactive polish |

### 12.3. Supporting Utilities

| File | Function |
|:--|:--|
| `utils/ast_parser.py` | Universal AST Parser — extracts code skeletons |
| `utils/evolution_ledger.py` | Writes to `EVOLUTION_LOG.jsonl` |
| `core/security.py` | Core security scanning utilities |
| `clean_fluff.py` | Token cleaner for conversational fluff removal |

---

