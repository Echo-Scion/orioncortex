# 🛡️ Meta-Agent & Foundation Infrastructure Audit Protocol

> **Purpose**: Algorithmic self-audit protocol for the `.agents/` ecosystem, CLI tools, hooks, local graph databases, and templates. Codified from the 13-phase infrastructure audit framework.

---

## 0. Pre-Audit Mechanical Gates (Run First)

Before performing any static or architectural analysis, execute these commands via `run_command`:
```bash
python .agents/scripts/orion.py verify
python .agents/scripts/orion.py preflight
```
- **Rule**: If either fails (Exit Code > 0), halt immediately and report findings as CRITICAL regressions.

---

## 1. The 14 Core Infrastructure Audit Vectors

When auditing the agent infrastructure itself, you MUST evaluate each file against these 14 vectors:

### Vector 1: Regression Invariants
- Verify that historical bug fixes remain intact.
- Ensure automated test harnesses and verifiers have not been commented out, bypassed, or deleted.

### Vector 2: Hooks & Concurrency Safety
- **Lockfile Debounce**: Verify that background daemons or heartbeat hooks use file-based PID lockfiles with explicit timestamps and process liveness checks (`psutil` or `os.kill(pid, 0)`).
- **Staleness Guard**: Verify that Omni-Buffer (`context.json`) rejects data older than 5 minutes (`300,000 ms`).
- **Loop Breaker**: Verify that pre-wake hooks cannot recursively invoke CLI commands that re-trigger the same hook (infinite spawning).

### Vector 3: Ingest, Linkify & Graph Integrity
- **Linkify Safety**: Ensure regex substitutions in `linkify.py` strictly escape special characters (`[`, `]`, `(`, `)`) to prevent corrupting markdown links into malformed wikilinks.
- **SQLite FTS5 Sync**: Ensure SQLite Full-Text Search (FTS5) triggers or manual sync routines keep the `pages_fts` index completely synchronized with `pages`.
- **Edge Deletion Isolation**: Removing an edge from the graph must NEVER cascade into deleting referenced shared nodes.

### Vector 4: Verifiers & Security Harnesses
- **Strict Normalized Paths**: Verifiers MUST use `os.path.normpath` and relative paths. **NEVER** permit basename fallbacks (which allow broken relative paths to pass if a file with the same name exists anywhere).
- **Binary Evidence Mandate**: Verifiers must exit with `code > 0` on any violation. Silent warnings with exit code 0 on structural failures are strictly forbidden.
- **Zero Secrets**: Ensure `.gitignore` and `preflight_check.py` prevent secret tokens, API keys, or private `.env` files from entering the repo.

### Vector 5: Database Schema & CLI Runtime
- **Schema Auto-Migration**: Verify that `orion_ops.py` checks table schemas and adds missing columns automatically (`access_count`, `last_accessed`, `importance`, `category`, `pillar`, `updated`, `fts_synced`, `ast_hash` in `pages`; `confidence`, `source_path` in `edges`).
- **Windows UTF-8 Encoding**: Every CLI command entrypoint in `.agents/scripts/commands/` MUST include:
  ```python
  if sys.platform == "win32":
      sys.stdout.reconfigure(encoding="utf-8")
      sys.stderr.reconfigure(encoding="utf-8")
  ```
  Prevents `UnicodeEncodeError` (CP1252/charmap) on Windows terminals.

### Vector 6: Hub-Spoke Sync & Templates
- **Hub Template Guard**: In `foundation.py`, `push-upstream` must detect placeholder sets (`{{...}}`) and refuse to overwrite generic hub templates with spoke-resolved assets unless `--force-hub-override` is provided.
- **Path Resolution**: `resolve_foundation_agents()` must always resolve to the `.agents/` directory, never the parent root.
- **Template Variables**: All variables in `TEMPLATE_VARS` (124 standard variables) must have fallback defaults. Deploy must not leave un-interpolated raw mustache tags in target spokes.
- **Lean Pillar Seeding**: `SEED_FILES` must seed all 4 Lean Pillar anchors (`BLUEPRINT.md`, `ROADMAP.md`, `STYLE_GUIDE.md`, `ARCHITECTURE.md`) into new spokes.

### Vector 7: DevSecOps Scripts & CLI Dispatchers
- **Dispatcher Registry**: In `orion.py`, every registered CLI subcommand must map to a real, imported function. No dead subcommands.
- **Exception Discipline**: CLI scripts must trap expected errors cleanly and exit with `sys.exit(1)`, never printing raw stack traces without an actionable diagnostic message.

### Vector 8: Rules, Contradictions & Token Economics
- **Contradiction-Free**: Cross-reference active rules for conflicting directives.
- **Token Efficiency**: Ensure scripts avoid reading files >100 lines when a targeted grep or line-range view suffices.
- **No Raw CLI String Patching**: Prohibit automated rewriting of source files via raw CLI strings (`sed`, `awk`, `python -c`). Use native editing tools.

### Vector 9: Skills & Workflows Integrity
- **Zero Ghost References**: Every target path in JIT routing tables (`GEMINI.md §4`, `AGENTS_INDEX.md`, `SKILL.md`) must physically exist on disk.
- **Valid Frontmatter**: Every `SKILL.md` must have valid YAML frontmatter with `name` and `description`.
- **Idempotency**: Workflows must be safe to re-run multiple times without causing duplicate state or data corruption.

### Vector 10: Darwinian Evolution & Genome Integrity
- **Set-Union Genome Merge**: Upstream synchronization of `.genome.json` must perform a set union of `evolved_skills`, `evolved_rules`, and `pruned_assets`, taking the maximum of `evolution_count`.
- **Consumer Isolation**: Private consumer projects or local testbeds must never leak into foundation genome or tracked git assets.

### Vector 11: Semantic Fact-Checking & Anti-Hallucination
- **Third-Party Library Grounding**: Forbid naming external frameworks or research papers (e.g. LightRAG, LangChain, Pinecone) in `README.md` and `docs/` unless the library is actually imported and executed in code. Disclaim conceptual inspiration explicitly.
- **Runtime Truth**: Disallow claiming multi-IDE compatibility (e.g. "Battle-tested on Cursor/Claude/Windsurf") without real-world test telemetry.
- **Command Grounding**: Every CLI command cited in markdown documentation must exist as a registered, working subcommand in `orion.py`.

### Vector 12: End-to-End Pipeline Cohesion (No Ghost Features)
- **Producer-Consumer Parity**: Every SQLite table and column created in `orion_ops.py` must have an active query consumer in `brain.py` or runtime dispatchers. Tables that are populated but never read during query execution are flagged as ghost features.
- **Query Path Verification**: Verify that graph relations stored in `edges` are actively traversed (e.g., 1-hop traversal) and injected into retrieval context during `brain sync`.

### Vector 13: Version Synchronization & Release Harmonization
- **Canonical Ground-Truth Uniformity**: `VERSION` is the absolute ground-truth string. Mismatches across `CHANGELOG.md`, `README.md` badge, `GEMINI.md` mandate, `AGENTS.template.md`, `core-guardrails.md`, `00-intro.md`, `DEPLOY_ME.md`, or `AGENT_IDENTITY.md` are classified as `HIGH` severity defects.
- **Mechanical Verification**: Audited automatically via `verify_agents.py`'s `check_version_synchronization`. Exit Code > 0 blocks release.

### Vector 14: Multi-System Matrix & Severity Scoring
When reporting findings, strictly categorize using the 4-tier matrix:
- **CRITICAL (C)**: Data loss, infinite hook loops, hub template pollution, unhandled crash in core CLI, hallucinated third-party dependencies.
- **HIGH (H)**: Broken routing targets, basename bypass in verifiers, silent exit 0 on failures, schema column drift, disconnected ghost pipelines, version synchronization drift.
- **MEDIUM (M)**: Windows encoding crashes on edge characters, fragile relative paths, unmapped template variables.
- **LOW (L)**: Cosmetic markdown discrepancies, unreferenced logs, outdated comments.
