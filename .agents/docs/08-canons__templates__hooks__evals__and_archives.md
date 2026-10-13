# VOLUME VIII: CANONS, TEMPLATES, HOOKS, EVALS, AND ARCHIVES

---

## Chapter 13: Ecosystem Canons (`canons/`)

### 13.1. 4-Layer Structure
```
canons/
├── ecosystems/         # Framework-specific
│   ├── flutter/        # 16 canon files (init, debug, release, state-map, ui-patterns, tests, etc.)
│   ├── react/          # 2 canon files (init, standards)
│   └── python/         # 2 canon files (init, standards)
├── global/             # Cross-framework
│   ├── core-architecture.md  # Constitution of all projects
│   ├── ai_brands.json        # Registry of supported IDEs
│   └── harnesses/            # Reusable verification scripts (action verifier, migration verifier, secrets scan)
├── local/              # Project-specific (empty in _foundation)
├── micro/              # Cheat-sheets for BUDGET models
│   ├── flutter.md      # Riverpod 2.x, Freezed, GoRouter syntax cheat-sheet
│   ├── pubspec.md      # Summary of Flutter pubspec.yaml
│   └── supabase.md     # Summary of Supabase patterns
```

### 13.2. `global/core-architecture.md` — 6 Core Principles
1. **Agent-First Design**: Code must be easy for AI to parse.
2. **Predictable Modularity**: Isolated modules > monoliths.
3. **Distributed Context**: Context at root AND app-level.
4. **Code-As-Harness**: Offload validations to verifier scripts.
5. **Unidirectional Data Flow**: Immutable state, mutations via actions/events.
6. **Strict Verification**: No features completed without mechanical verification.

## Chapter 14: Templates (`templates/`)

### 14.1. 12 Template Files

| Template | Target | Purpose |
|:--|:--|:--|
| `AGENTS.template.md` | Root project (`GEMINI.md`/`CLAUDE.md`) | Multi-AI instruction generator (DRY source) |
| `PROJECT_SCAFFOLD.template.md` | Architecture & Blueprint | Master prompt for scaffolding new projects + 82-file mapping |
| `MEMORY.template.md` | State tracking | SaaS state tracking & session handoff |
| `TASK_PLANNING.template.md` | Checklists | Execution, roadmap, atomic tasks |
| `STYLE_GUIDE.template.md` | UI/UX tokens | Visual style guide |
| `ORION_SCHEMA.template.md` | `.orion/` configuration | Graph schema |
| `agent-identity-template.md` | Agent identity | Identity bootstrap profile |
| `custom-agent.template.md` | New agent | Scaffold for custom AI agent |
| `custom-rule.template.md` | New rule | Scaffold for behavioral rule |
| `github-native-structure.md` | GitHub | Canonical GitHub folder structure guide |
| `startup_knowledge_base.md` | Knowledge | Auto-populating instructions for SaaS domains |
| `TEMPLATES.md` | Documentation | Master registry of all template definitions |

## Chapter 15: Hooks (`hooks/`)

### 15.1. `pre-agent-wake.py`
**Omni-Buffer Hook.** Called by IDE before AI starts its turn. Functions:
1. Receives arguments `--active-file`, `--terminal-error`, `--ide-source`, `--user-intent`.
2. Writes state to `context.json` atomically (temp file → `os.replace`).
3. Checks `LEARNINGS.md` for unprocessed learning entries. If >= 3, sets `evolution_overdue = True` in `context.json`.
4. The active agent detects `evolution_overdue: true` upon bootstrap and triggers `.agents/skills/self-evolve/SKILL.md`.

### 15.2. `post-commit` (Git Hook)
**Proactive Synchronization.** Automatically triggered by Git upon every commit. Functions:
1. Runs `python .agents/scripts/orion.py brain sync`.
2. Ensures the AI's contextual knowledge base and Graph representation are updated asynchronously without developer friction.

## Chapter 16: Evaluators (`evals/`)

### 16.1. `audit_aesthetics.py`
**CI/CD Gatekeeper for Aesthetics.** Scans `.dart`, `.tsx`, `.jsx`, `.css` files:
- **Check 1**: Detects generic colors (`Colors.red`, `Colors.blue`). Error: must use design tokens.
- **Check 2**: Detects inline style with generic colors. Error.
- **Check 3**: If > 5 raw hex codes, warning: extract to semantic tokens.
- **Check 4**: If file is a UI component but NO animation primitives are used (`AnimatedContainer`, `framer-motion`, `transition-all`), warning: add micro-interactions.

Exit Code 1 = fail → agent is forbidden from proceeding without fixes.

### 16.2. `evals.json`
Benchmark/evaluation configuration for testing AI models.

## Chapter 17: Documentation (`docs/`)
The `.agents/docs/` directory contains the complete 12-volume Master Encyclopedia of the ecosystem:
- `00-intro.md`: Master encyclopedia preface, purpose, and version.
- `01-theoretical_foundation.md`: Core LLM failure modes and deterministic mitigations.
- `02-system_architecture.md`: Master BIOS, Omni-Buffer, RTK, and State Machine.
- `03-local_rag_brain.md`: Local RAG, FTS5, AST parser, and NanoBrain architecture.
- `04-rule_library___rules.md`: Complete rule library catalog and enforcement protocols.
- `05-skill___persona___skills.md`: 16 skill personas, domains, and reference guides.
- `06-workflow___sop.md`: 18 standard operating procedures and execution loops.
- `07-python_scripts___scripts.md`: Orion CLI command matrix and supporting utilities.
- `08-canons__templates__hooks__evals__and_archives.md`: Canons, templates, hooks, and evals.
- `09-darwinian_evolution_lifecycle.md`: Friction mining, canary deployment, and genetic ledger.
- `10-deployment_flow_to_new_projects.md`: Step-by-step spoke deployment procedures.
- `11-complete_glossary.md`: Canonical terminology and operational definitions.

## Chapter 18: Quality & Evals Benchmarks
Model benchmarks and evaluation configs are maintained in `evals/` (`evals.json`, `audit_aesthetics.py`) and `scripts/commands/track_budget.py` for model tier and Small Model Superiority telemetry.

## Chapter 19: Archive (`archive/`)
Contains `README.md`, `orion_mcp.py` (legacy/experimental MCP server), and `workflows/` (safely preserved 18 legacy procedural workflows from pre-v0.0.5 architecture).

## Chapter 20: Root `.agents` Files

### 20.1. `AGENTS_INDEX.md`
Master map listing all Rules, Skills, Workflows, and Canons with relative paths.

### 20.2. `DEPLOY_ME.md`
Plug-and-play instructions to deploy Foundation to a new project. Covers:
- Mandatory Q&A (framework, language).
- Gitignore pre-flight.
- Execution command: `python .agents/scripts/orion.py foundation deploy --target ... --framework ... --language ...`
- Safe Auto-Ingest (strictly forbidden to ingest the root directory).

### 20.3. `LEARNINGS.md`
**Collective memory.** YAML format per entry: `date`, `task_id`, `tier`, `severity`, `issue`, `root_cause`, `solution`, `debt_warning`. Contains real post-mortems (VRAM OOM, workflow violations, smart ingest architecture).

### 20.4. `EVOLUTION_LOG.jsonl`
Append-only genomic ledger. Each mutation, bug fix, and extracted pattern is written as a JSON line:
```json
{
  "timestamp": "2026-06-12T14:30:00Z",
  "mutation": "Banned usage of generic 'any' type in TS DTOs.",
  "friction_source": "Runtime crash on malformed JSON payload.",
  "fitness_delta": "+15%",
  "genome_hash": "a1b2c3d4e5"
}
```

### 20.5. `.genome.json` (139 bytes)
Genomic fingerprint that can be imported to a new project so the AI immediately inherits past lessons.

### 20.6. `.project_manifest.json` (70 bytes)
Project metadata: framework, language, project name.

### 20.7. `.deployed_ais` (414 bytes)
Registry of IDEs that have received Foundation deployment.

### 20.8. `.foundation_path` (47 bytes)
Absolute path to the `_foundation` repo. Used by deployment scripts.

---

